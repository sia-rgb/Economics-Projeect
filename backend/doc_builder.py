from __future__ import annotations

import re
from io import BytesIO
from typing import List

from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn

from epub_processing import Article


def _set_font_chinese_english(font, chinese_font: str, english_font: str):
    """设置字体的中文字体和英文字体。"""
    font.name = english_font
    # 通过XML直接设置中文字体
    r_fonts = font._element.find(qn('w:rFonts'))
    if r_fonts is None:
        from docx.oxml import parse_xml
        r_fonts = parse_xml(r'<w:rFonts xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
        font._element.append(r_fonts)
    r_fonts.set(qn('w:eastAsia'), chinese_font)  # 中文字体
    r_fonts.set(qn('w:ascii'), english_font)  # 英文字体
    r_fonts.set(qn('w:hAnsi'), english_font)  # 高ANSI字符字体


def _extract_article_title(title: str) -> str:
    """从标题中提取真正的文章标题，去除网址和前缀，支持多行。"""
    # 先统一处理换行符，合并为单行以便正则匹配
    title_normalized = re.sub(r'\s+', ' ', title).strip()
    
    # 先去除网址模式（feed_*/article_*/index_*.html 等）
    title_normalized = re.sub(r'feed_\d+/article_\d+/index_\w+\.html', '', title_normalized)
    title_normalized = re.sub(r'[a-zA-Z0-9_/]+\.html', '', title_normalized)
    
    # 优先提取《》中的内容（支持跨行）
    match = re.search(r'《([^》]+)》', title_normalized)
    if match:
        return match.group(1).strip()
    
    # 提取【文章标题】** :或【文章标题】：后面的内容（支持跨行）
    match = re.search(r'【文章标题】\*?\*?\s*[：:]\s*(.+)', title_normalized)
    if match:
        extracted = match.group(1).strip()
        # 如果提取的内容还包含《》，提取《》中的内容
        inner_match = re.search(r'《([^》]+)》', extracted)
        if inner_match:
            return inner_match.group(1).strip()
        return extracted
    
    # 去除【文章标题】等前缀标记
    title_normalized = re.sub(r'【文章标题】\*+\s*[：:]\s*', '', title_normalized)
    title_normalized = title_normalized.strip()
    
    # 如果还有残留的网址或路径，继续清理
    title_normalized = re.sub(r'^[a-zA-Z0-9_/\.]+', '', title_normalized).strip()
    
    # 如果清理后还有内容，返回清理后的内容
    if title_normalized:
        return title_normalized
    
    return "未命名文章"


# 刊名等通用标题，若提取到这些则视为无效，需从引言兜底
_GENERIC_TITLES = frozenset({"经济学人", "the economist", "economist", "《经济学人》"})


def _derive_title_from_intro(analysis: str) -> str | None:
    """从【引言】段落提取首句或前若干字作为兜底标题。综述类引言优先提取简短栏目名。"""
    match = re.search(r'【引言】\*?\*?\s*[：:]\s*(.+?)(?=\n\n|【|$)', analysis, re.DOTALL)
    if not match:
        return None
    intro = match.group(1).strip()
    if not intro:
        return None
    intro_start = intro[:80]
    # 综述类引言：提取简短栏目名
    if re.search(r"全球商业", intro_start):
        return "全球商业动态"
    if re.search(r"全球市场", intro_start):
        return "全球市场动态"
    if re.search(r"全球政治", intro_start):
        return "全球政治动态"
    if re.search(r"本周全球", intro_start):
        return "本周全球商业动态"
    # 取首句（以。！？为界）或前 40 字
    for sep in "。", "！", "？", "，":
        idx = intro.find(sep)
        if idx > 0 and idx <= 50:
            return intro[: idx + 1].strip()
    return intro[:40].strip() + ("…" if len(intro) > 40 else "") if intro else None


def _is_roundup_intro(analysis: str) -> bool:
    """判断引言是否为综述类（本周全球、全球市场等）。"""
    match = re.search(r'【引言】\*?\*?\s*[：:]\s*(.+?)(?=\n\n|【|$)', analysis, re.DOTALL)
    if not match:
        return False
    intro = (match.group(1) or "")[:80]
    return bool(re.search(r"本周全球|全球市场|全球商业|全球政治", intro))


def _is_specific_topic_title(title: str) -> bool:
    """判断标题是否为具体议题（如法案、政策名），易与综述类文章混淆。"""
    if not title or len(title) < 2:
        return False
    return bool(re.search(r"法案$|法$", title))


def _extract_title_from_analysis(analysis: str) -> str | None:
    """从 DeepSeek 分析结果中提取【文章标题】后的中文标题。"""
    if not analysis or not analysis.strip():
        return None
    # 匹配【文章标题】**：或【文章标题】：后面的内容（可能跨行）
    match = re.search(r'【文章标题】\*?\*?\s*[：:]\s*(.+)', analysis, re.DOTALL)
    if not match:
        return None
    extracted = match.group(1).strip()
    # 优先取《》中的内容
    inner = re.search(r'《([^》]+)》', extracted)
    if inner:
        first_line = inner.group(1).strip()
    else:
        first_line = extracted.split('\n')[0].strip()
    if not first_line:
        return None
    # 若为刊名等通用标题，尝试从引言兜底
    if first_line in _GENERIC_TITLES or first_line.lower() in _GENERIC_TITLES:
        return _derive_title_from_intro(analysis)
    # 综述类引言 + 具体议题式标题（如「叛乱法」「就业权利法案」）：强制使用引言兜底
    if _is_specific_topic_title(first_line) and _is_roundup_intro(analysis):
        derived = _derive_title_from_intro(analysis)
        if derived:
            return derived
        # 如果 _derive_title_from_intro 返回 None，仍然不应该使用具体议题式标题
        # 尝试从引言中提取首句作为兜底
        intro_match = re.search(r'【引言】\*?\*?\s*[：:]\s*(.+?)(?=\n\n|【|$)', analysis, re.DOTALL)
        if intro_match:
            intro = intro_match.group(1).strip()
            # 提取首句（以。！？为界）或前 40 字
            for sep in "。", "！", "？":
                idx = intro.find(sep)
                if idx > 0 and idx <= 50:
                    return intro[: idx + 1].strip()
            if intro:
                return intro[:40].strip() + ("…" if len(intro) > 40 else "")
    return first_line


def build_docx_from_analyses(
    analyses: List[str],
    articles: List[Article],
) -> BytesIO:
    """将所有文章的中文分析结果写入单一 Word 文档并返回内存流。"""
    if len(analyses) != len(articles):
        raise ValueError("analyses 与 articles 数量不一致。")

    doc = Document()

    # 设置全局字体：中文使用微软雅黑，英文使用Times New Roman
    style = doc.styles["Normal"]
    font = style.font
    _set_font_chinese_english(font, "微软雅黑", "Times New Roman")
    font.size = Pt(11)
    
    # 设置标题字体：中文使用微软雅黑，英文使用Times New Roman
    heading_style = doc.styles["Heading 1"]
    heading_font = heading_style.font
    _set_font_chinese_english(heading_font, "微软雅黑", "Times New Roman")

    for article, analysis in zip(articles, analyses, strict=True):
        # 优先从分析结果中提取标题，否则用 EPUB 元数据
        heading = _extract_title_from_analysis(analysis) or _extract_article_title(article.title)
        doc.add_heading(heading, level=1)

        # 将分析文本按空行拆成段落
        chunks = [chunk.strip() for chunk in analysis.split("\n\n") if chunk.strip()]
        if not chunks:
            continue

        for chunk in chunks:
            # 跳过【文章标题】段落，避免与标题重复
            if re.match(r'^【文章标题】\*?\*?\s*[：:]', chunk):
                continue
            doc.add_paragraph(chunk)

        # 章节之间空一页或空几行，这里简单空两行
        doc.add_paragraph()
        doc.add_paragraph()

    stream = BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream

