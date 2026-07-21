import re
from copy import copy
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# Review column list and their positions
REVIEW_COLUMNS = {
    'v1': [
        '实务内容（官方）', '实务内容（行业通用）', '实务内容（内部口径）',
        '参考依据（官方）', '参考依据（行业权威）', '参考依据（行业常规）',
    ],
    'v2': [
        '官方规则', '行业通用', '官方网站', '权威网站',
    ],
}

STATUS_BG_COLORS = {
    '待审阅': 'F0F0F0',
    '已确认': '36cf50',
    '需修改': 'ffb700',
    '待讨论': '722ed1',
}

GREEN = '548235'
RED = 'C00000'
BLUE = '2E75B5'


def _html_to_cell_parts(html_text):
    """Parse Quill HTML and return list of (text, font_dict) tuples.
    Each font_dict contains openpyxl Font constructor kwargs."""
    if not html_text:
        return [('', {})]

    # Remove <p> and <br> tags (convert to newlines)
    text = html_text.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
    text = re.sub(r'</p>\s*<p[^>]*>', '\n', text)
    text = re.sub(r'</?p[^>]*>', '', text)

    parts = []
    _parse_tags(text, 0, {}, parts)
    return parts if parts else [('', {})]


def _parse_tags(s, offset, current_fmt, parts):
    """Recursively parse HTML string, building (text, font) segments."""
    i = offset
    while i < len(s):
        if s[i] == '<':
            end = s.find('>', i)
            if end == -1:
                # No closing bracket, treat rest as plain text
                parts.append((s[i:], dict(current_fmt)))
                return

            tag_content = s[i + 1:end]
            tag_name = tag_content.split()[0].lower().rstrip('/')

            # Self-closing or void elements
            if tag_content.endswith('/') or tag_name in ('br', 'hr', 'img'):
                if tag_name == 'br':
                    parts.append(('\n', dict(current_fmt)))
                i = end + 1
                continue

            # Closing tag
            if tag_name.startswith('/'):
                return  # Return to parent, restoring parent font

            # Opening tag — build font modifiers
            new_fmt = dict(current_fmt)
            if tag_name in ('strong', 'b'):
                new_fmt['bold'] = True
            elif tag_name in ('em', 'i'):
                new_fmt['italic'] = True
            elif tag_name == 'u':
                new_fmt['underline'] = 'single'
            elif tag_name in ('s', 'strike', 'del'):
                new_fmt['strikethrough'] = True
            elif tag_name == 'a':
                new_fmt['underline'] = 'single'
                href_match = re.search(r'href="([^"]*)"', tag_content)
                if href_match:
                    new_fmt['color'] = '0563C1'

            # Inline style attributes
            style_match = re.search(r'style="([^"]*)"', tag_content)
            if style_match:
                style = style_match.group(1)
                if 'color' in style:
                    # Support both hex (#FF0000) and rgb(r, g, b) formats
                    hex_match = re.search(r'color:\s*(#[0-9a-fA-F]{6})', style)
                    rgb_match = re.search(r'color:\s*rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', style)
                    if hex_match:
                        new_fmt['color'] = hex_match.group(1).lstrip('#')
                    elif rgb_match:
                        r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
                        new_fmt['color'] = f'{r:02X}{g:02X}{b:02X}'
                if 'background-color' in style:
                    hex_match = re.search(r'background-color:\s*(#[0-9a-fA-F]{6})', style)
                    rgb_match = re.search(r'background-color:\s*rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', style)
                    if hex_match:
                        new_fmt['color'] = hex_match.group(1).lstrip('#')
                    elif rgb_match:
                        r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
                        new_fmt['color'] = f'{r:02X}{g:02X}{b:02X}'

            # Recursively parse inner content with new format
            closing = '</' + tag_name + '>'
            close_pos = s.find(closing, end + 1)
            if close_pos == -1:
                # No closing tag, treat inner as plain
                inner_text = s[end + 1:]
                if inner_text:
                    parts.append((inner_text, dict(new_fmt)))
                return
            else:
                _parse_tags(s, end + 1, new_fmt, parts)
                i = close_pos + len(closing)
        else:
            # Plain text
            next_tag = s.find('<', i)
            if next_tag == -1:
                parts.append((s[i:], dict(current_fmt)))
                return
            text_seg = s[i:next_tag]
            if text_seg:
                parts.append((text_seg, dict(current_fmt)))
            i = next_tag


def generate_review_excel(input_path, output_path, review_map, format_version='v1'):
    """Generate the reviewed Excel file."""
    review_cols = REVIEW_COLUMNS.get(format_version, REVIEW_COLUMNS['v1'])
            col_positions[h] = headers.index(h) + 1

    sorted_cols = sorted(col_positions.items(), key=lambda x: x[1], reverse=True)

    for field_type, base_col in sorted_cols:
        insert_col = base_col + 1
        ws.insert_cols(insert_col)

        header_cell = ws.cell(row=1, column=insert_col)
        header_cell.value = f"{field_type}_校验列"
        orig_header = ws.cell(row=1, column=base_col)
        header_cell.font = copy(orig_header.font)
        header_cell.alignment = copy(orig_header.alignment)

        for row in range(2, ws.max_row + 1):
            key = (row, field_type)
            if key in review_map:
                rf = review_map[key]
                cell = ws.cell(row=row, column=insert_col)

                bg_color = STATUS_BG_COLORS.get(rf.status)
                if bg_color and rf.status != '待审阅':
                    cell.fill = PatternFill(start_color=bg_color,
                                            end_color=bg_color, fill_type='solid')

                content = rf.changed_content
                if content:
                    if '<' in content:
                        _apply_html_to_cell(cell, content)
                    else:
                        cell.value = content

    for col in range(1, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(col)].width = 25

    wb.save(output_path)
    wb.close()


def _apply_html_to_cell(cell, html_text):
    """Apply HTML-formatted text to an openpyxl cell as rich text."""
    from openpyxl.cell.text import InlineFont
    from openpyxl.cell.rich_text import TextBlock, CellRichText

    parts = _html_to_cell_parts(html_text)

    # Check if any formatting exists
    has_any_fmt = False
    for text, fmt in parts:
        if fmt:
            has_any_fmt = True
            break

    if not has_any_fmt:
        cell.value = ''.join(p[0] for p in parts)
        return

    # Build rich text
    rich_parts = []
    for text, fmt in parts:
        if not text:
            continue
        if fmt:
            # Map to openpyxl font kwargs
            font_args = {}
            if fmt.get('bold'):
                font_args['b'] = True
            if fmt.get('italic'):
                font_args['i'] = True
            if fmt.get('underline'):
                font_args['u'] = 'single'
            if fmt.get('strikethrough'):
                font_args['strike'] = True
            if fmt.get('color'):
                font_args['color'] = fmt['color']
            if font_args:
                f = InlineFont(**font_args)
                rich_parts.append(TextBlock(f, text))
            else:
                rich_parts.append(text)
        else:
            rich_parts.append(text)

    if rich_parts:
        cell.value = CellRichText(*rich_parts)
