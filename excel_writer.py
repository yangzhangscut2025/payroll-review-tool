import re
import json
import requests
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
    'v3': [
        '实务内容（官方）', '实务内容（行业通用）',
        '参考依据（官方）', '参考依据（行业权威）',
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


BATCH_SIZE = 20  # items per API call

LANG_MAP = {
    'en_English': '英文',
}

TRANSLATION_PROMPT = (
    '你是薪酬合规领域的专业翻译。请将以下审阅批注从中文翻译为{target_lang}。'
    '规则：\n'
    '1. 法律/薪酬/税务术语必须准确，不得意译或简化\n'
    '2. 文本中的 {{__T0__}} {{__T1__}} 等占位符必须原样保留，不能修改或删除\n'
    '3. 编号、数字、百分比、日期、法律条文编号保持原格式\n'
    '4. 输出纯 JSON 数组，每条严格对应输入的一条，不要任何解释文字\n'
    '输入：\n{items}\n输出：'
)

TAG_PATTERN = re.compile(r'(<[^>]+>)')


def _protect_html(text):
    """Replace HTML tags with placeholders {__Tn__}, return (protected_text, tag_map)."""
    tags = TAG_PATTERN.findall(text)
    tag_map = {}
    for i, tag in enumerate(tags):
        placeholder = f'{{__T{i}__}}'
        text = text.replace(tag, placeholder, 1)
        tag_map[placeholder] = tag
    return text, tag_map


def _restore_html(text, tag_map):
    """Restore HTML tags from placeholders."""
    for placeholder, tag in tag_map.items():
        text = text.replace(placeholder, tag)
    return text


def _translate_batch(items, target_lang, api_key, api_url, model, progress_callback=None):
    """Translate a list of Chinese texts to target language using DeepSeek API.
    HTML tags are protected with placeholders during translation."""
    if not items or not api_key:
        return items

    # Protect HTML tags in each item
    protected_items = []
    tag_maps = []
    for text in items:
        if '<' in text:
            protected, tag_map = _protect_html(text)
            protected_items.append(protected)
            tag_maps.append(tag_map)
        else:
            protected_items.append(text)
            tag_maps.append({})

    # Split into batches
    batches = [protected_items[i:i + BATCH_SIZE] for i in range(0, len(protected_items), BATCH_SIZE)]
    total_batches = len(batches)
    translated = []

    for batch_idx, batch in enumerate(batches):
        if progress_callback:
            progress_callback(batch_idx + 1, total_batches)
        items_json = json.dumps(batch, ensure_ascii=False)
        prompt = TRANSLATION_PROMPT.format(
            target_lang=target_lang,
            items=items_json
        )
        try:
            resp = requests.post(
                api_url,
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.1,
                    'max_tokens': 4096,
                },
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
            content = result['choices'][0]['message']['content'].strip()
            if content.startswith('```'):
                content = content.split('\n', 1)[1]
                if content.endswith('```'):
                    content = content.rsplit('\n', 1)[0]
            parsed = json.loads(content)
            translated.extend(parsed if isinstance(parsed, list) else batch)
        except Exception as e:
            translated.extend(batch)

    # Restore HTML tags
    result = []
    for i, text in enumerate(translated):
        if tag_maps[i]:
            result.append(_restore_html(text, tag_maps[i]))
        else:
            result.append(text)
    return result


def generate_review_excel(input_path, output_path, review_map, format_version='v1', progress_callback=None):
    """Generate the reviewed Excel file — processes ALL sheets.
    progress_callback(pct, sheet_name, detail) called during processing."""
    _state = {'sheet': ''}

    def _progress(pct, detail):
        if progress_callback:
            progress_callback(pct, _state['sheet'], detail)

    review_cols = REVIEW_COLUMNS.get(format_version, REVIEW_COLUMNS['v1'])
    wb = load_workbook(input_path)

    # Identify which sheets need translation (non-Chinese)
    translate_sheets = [s for s in wb.sheetnames if s in LANG_MAP]

    # Pre-translate: collect all changed_content, translate once per language
    translations = {}  # {lang: {key: translated_text}}
    if translate_sheets:
        from config import Config
        api_key = Config.DEEPSEEK_API_KEY
        api_url = Config.DEEPSEEK_API_URL
        model = Config.DEEPSEEK_MODEL

        if api_key:
            # Collect all (key, text) pairs that have content
            text_entries = [
                (key, rf.changed_content)
                for key, rf in review_map.items()
                if rf.changed_content and rf.changed_content.strip()
            ]
            if text_entries:
                keys, texts = zip(*text_entries)
                texts = list(texts)
                total_items = len(texts)
                total_batches = (total_items + BATCH_SIZE - 1) // BATCH_SIZE

                for sheet_name in translate_sheets:
                    lang = LANG_MAP.get(sheet_name, sheet_name)
                    _progress(10, f'翻译{lang}...')
                    translated_texts = _translate_batch(
                        texts, lang, api_key, api_url, model,
                        progress_callback=lambda i, t: _progress(
                            10 + int(80 * (i / t) / len(translate_sheets)),
                            f'翻译{lang} {i}/{t}'
                        ) if progress_callback else None
                    )
                    if len(translated_texts) == len(texts):
                        translations[sheet_name] = dict(zip(keys, translated_texts))

    # Only process Chinese and English sheets; skip local-language sheets
    target_sheets = ['zh_Chinese'] + list(LANG_MAP.keys())
    total_sheets = len([s for s in wb.sheetnames if s in target_sheets])
    sheet_idx = 0

    for ws in wb.worksheets:
        if ws.title not in target_sheets:
            continue

        _state['sheet'] = ws.title
        sheet_idx += 1
        base_pct = 90 if not translate_sheets else 10 + int(80 / len(translate_sheets)) * len(translate_sheets)
        _progress(base_pct + int((sheet_idx / total_sheets) * (100 - base_pct)),
                  f'写入{ws.title}...')
        headers = []
        for col in range(1, ws.max_column + 1):
            val = ws.cell(row=1, column=col).value
            headers.append(str(val).strip() if val else '')

        col_positions = {}
        for h in headers:
            if h in review_cols:
                col_positions[h] = headers.index(h) + 1

        sorted_cols = sorted(col_positions.items(), key=lambda x: x[1], reverse=True)
        is_translated = ws.title in translations

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
                    # Use translated content if available for this sheet
                    if is_translated and key in translations.get(ws.title, {}):
                        content = translations[ws.title][key]

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
