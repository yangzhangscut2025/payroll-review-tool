"""关键词溯源：提取关键数据，在离线MD中搜索匹配。"""
import os
import re

AMOUNT_RE = re.compile(
    r'[€$£¥]\s*\d+[.,]?\d*\s*|'
    r'\d+[.,]?\d*\s*(?:欧元|美元|英镑|日元|元|%|％|percent|per\s+cent|/小时|/月|/年|小时|个月|周|天)',
    re.IGNORECASE
)
DATE_RE = re.compile(
    r'\d{4}\s*[-/年]\s*\d{1,2}\s*[-/月]\s*\d{1,2}|'
    r'\d{1,2}\s*[-/月]\s*\d{4}|'
    r'\d{4}\s*年\d{1,2}\s*月\d{1,2}日?|'
    r'\d{4}\s*[-/]\s*\d{1,2}|'
    r'[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}',
    re.IGNORECASE
)
NUMBER_RE = re.compile(
    r'\d{2,}(?![./])(?!\d)|'
    r'\d+\s*(?:岁|周|月|年|天|小时|次|倍|条|项|人|份|级)'
)


def extract_keywords(text):
    """提取数字、日期、金额等关键数据点。"""
    if not text:
        return []
    kws = set()
    for regex in [AMOUNT_RE, DATE_RE, NUMBER_RE]:
        for m in regex.finditer(text):
            kw = m.group().strip()
            if len(kw) >= 2:
                kws.add(kw)
    return sorted(kws, key=len, reverse=True)[:15]


def split_sentences(text):
    """按序号或换行拆分声明。"""
    if not text:
        return []
    parts = re.split(r'(?:(?:^|\n)\s*(?:\d+[\.\)、．]\s*))', text)
    parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [text.strip()]


def search_md_files(md_dir, keywords):
    """在MD目录中搜索关键词。返回 {keyword: [{file, contexts}]}"""
    results = {}
    if not os.path.isdir(md_dir):
        return results
    md_files = [f for f in os.listdir(md_dir) if f.endswith('.md')]
    if not md_files:
        return results

    for kw in keywords:
        hits = []
        for fname in sorted(md_files):
            path = os.path.join(md_dir, fname)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                continue
            search_kw = kw.replace(',', '').replace('，', '').replace(' ', '').lower()
            search_text = content.replace(',', '').replace('，', '').replace(' ', '').lower()
            if search_kw in search_text:
                contexts = _get_contexts(content, kw)
                display_name = fname.replace('.md', '.html')
                hits.append({'file': display_name, 'contexts': contexts})
        if hits:
            results[kw] = hits
    return results


def _get_contexts(text, keyword, radius=100):
    """提取关键词每次出现的上下文。"""
    ctxs = []
    idx = 0
    kw_low = keyword.lower()
    text_low = text.lower()
    for _ in range(3):
        idx = text_low.find(kw_low, idx)
        if idx == -1:
            break
        start = max(0, idx - radius)
        end = min(len(text), idx + len(keyword) + radius)
        snip = text[start:end].strip()
        if start > 0:
            snip = '…' + snip
        if end < len(text):
            snip += '…'
        ctxs.append(snip)
        idx += len(keyword)
    return ctxs


def trace_one_field(text, md_dir):
    """溯源一个实务内容字段。返回 [{sentence, keywords: [{kw, found, hits}]}]"""
    sentences = split_sentences(text)
    result = []
    for sent in sentences:
        kws = extract_keywords(sent)
        if not kws:
            result.append({'sentence': sent, 'keywords': []})
            continue
        matches = search_md_files(md_dir, kws)
        kw_list = []
        for kw in kws:
            kw_list.append({'kw': kw, 'found': kw in matches, 'hits': matches.get(kw, [])})
        result.append({'sentence': sent, 'keywords': kw_list})
    return result
