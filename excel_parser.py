import openpyxl

# Required column names (exact match)
REQUIRED_COLUMNS = [
    'l1_标题',
    'l1_说明',
    'l2_标题',
    'l2_说明',
    '实务内容（官方）',
    '实务内容（行业通用）',
    '实务内容（内部口径）',
    '参考依据（官方）',
    '参考依据（行业权威）',
    '参考依据（行业常规）',
    '属性',
    '状态',
    '内部计算链路',
]

REVIEW_COLUMNS = [
    '实务内容（官方）',
    '实务内容（行业通用）',
    '实务内容（内部口径）',
    '参考依据（官方）',
    '参考依据（行业权威）',
    '参考依据（行业常规）',
]


def get_merged_cell_map(ws):
    """Build a map from merged cell ranges to the top-left value."""
    merged = {}
    for merge_range in ws.merged_cells.ranges:
        min_col = merge_range.min_col
        min_row = merge_range.min_row
        top_left_val = ws.cell(row=min_row, column=min_col).value
        for row in range(merge_range.min_row, merge_range.max_row + 1):
            for col in range(merge_range.min_col, merge_range.max_col + 1):
                merged[(row, col)] = top_left_val
    return merged


def parse_excel(filepath, project_id, db):
    """Parse uploaded Excel and create ReviewField records."""
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active

    # Read headers
    headers = []
    for col in range(1, ws.max_column + 1):
        val = ws.cell(row=1, column=col).value
        if val:
            val = str(val).strip()
        headers.append(val)

    # Validate required columns
    for i, req in enumerate(REQUIRED_COLUMNS):
        if i >= len(headers) or headers[i] != req:
            raise ValueError(
                f"表格结构不符合预期，请检查列名是否完整且完全匹配。"
                f"列 {i+1}：期望「{req}」，实际「{headers[i] if i < len(headers) else '无'}」"
            )

    # Build column index map for review columns
    col_map = {}
    for c_idx, h in enumerate(headers):
        if h in REVIEW_COLUMNS:
            col_map[h] = c_idx + 1  # 1-indexed

    # Build merged cell map for l1/l2 fill-down
    merged_map = get_merged_cell_map(ws)

    # Parse data rows
    from models import ReviewField
    l1_set = set()
    l2_set = set()
    total_fields = 0

    for row in range(2, ws.max_row + 1):
        # Check if row is empty
        row_has_data = False
        for c in range(1, min(14, ws.max_column + 1)):
            if ws.cell(row=row, column=c).value is not None:
                row_has_data = True
                break
        if not row_has_data:
            continue

        # Get l1/l2 with merged cell fill-down
        l1_title = ws.cell(row=row, column=1).value
        if not l1_title:
            l1_title = merged_map.get((row, 1), '')
        l1_title = str(l1_title).strip() if l1_title else ''

        l2_title = ws.cell(row=row, column=3).value
        if not l2_title:
            l2_title = merged_map.get((row, 3), '')
        l2_title = str(l2_title).strip() if l2_title else ''

        if not l1_title or not l2_title:
            continue

        l1_set.add(l1_title)
        l2_set.add(f"{l1_title}|{l2_title}")

        # Create review fields for each review column
        for field_type in REVIEW_COLUMNS:
            col = col_map.get(field_type)
            if not col:
                continue
            original = ws.cell(row=row, column=col).value
            original_str = str(original).strip() if original else ''

            rf = ReviewField(
                project_id=project_id,
                row_index=row,
                module_l1=l1_title,
                module_l2=l2_title,
                field_type=field_type,
                original_content=original_str,
                changed_content=original_str,  # Initial copy
                status='待审阅',
            )
            db.session.add(rf)
            total_fields += 1

    wb.close()
    return {
        'l1_count': len(l1_set),
        'l2_count': len(l2_set),
        'total_fields': total_fields,
    }
