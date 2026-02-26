from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


@dataclass
class Article:
    title: str
    content: str


# 全球商业/市场/政治动态、漫画、读者来信：提取时跳过（中英文关键词）
ROUNDUP_SKIP_KEYWORDS = (
    "global business", "business this week", "世界商业", "全球商业", "全球商业动态",
    "global market", "markets", "market this week", "finance", "全球市场", "全球市场动态",
    "global politics", "politics this week", "政治动态", "全球政治", "全球政治动态",
    "cartoon", "comic", "漫画", "weekly cartoon",
    "letters", "读者来信",
)

# 供口播稿 prompt 使用的跳过类型短名称（与 ROUNDUP_SKIP_KEYWORDS 语义一致，单一数据源）
SKIP_CATEGORIES_PROMPT = (
    "全球商业动态",
    "全球市场动态",
    "全球政治动态",
    "漫画 (cartoon / comic)",
    "读者来信 (Letters to the editor)",
)


def get_audio_script_skip_rules_text() -> str:
    """返回口播稿 system message 中「跳过规则」段落的完整文案，供 deepseek_client 嵌入。"""
    bullets = "\n".join(f"- {c}" for c in SKIP_CATEGORIES_PROMPT)
    return (
        "# 跳过规则 (Skip Rules)\n"
        "若原文属于以下类型之一，则**不生成口播正文**，仅输出一行且仅此一行：**【不生成口播稿】**（无其他内容）。\n"
        f"{bullets}"
    )


# 正文首行至少多少字符才视为正文（否则视为标题与正文之间的短句/导语并删除）
MIN_BODY_LINE_CHARS = 50

# 无意义的占位/导航标题，不得作为 Article.title（含 TOC 常见“上一项/下一项/文章”等）
_PLACEHOLDER_TITLE = frozenset({
    "标题", "title",
    "上一项", "下一项", "下一篇", "上一篇",
    "文章", "article",
    "未命名文章",
})


def _is_placeholder_title(s: str) -> bool:
    """是否为无意义的「标题」占位，不得作为真实标题使用。"""
    if not s or not s.strip():
        return True
    cleaned = re.sub(r"^\*+|\*+$", "", s).strip()
    return cleaned.lower() in _PLACEHOLDER_TITLE


def _is_roundup_or_dynamic_section(name: str) -> bool:
    """栏目名是否为需跳过的全球商业/市场/政治动态、漫画、读者来信。"""
    lower = name.lower().strip()
    return any(
        kw in lower or kw in name
        for kw in ROUNDUP_SKIP_KEYWORDS
    )


# 为观察《经济学人》HTML 结构时可设为 True，将每篇前 2000 字符写入 .cursor/epub_html_samples/
DEBUG_EPUB_HTML = os.environ.get("DEBUG_EPUB_HTML", "").strip().lower() in ("1", "true", "yes")


def _normalize_href(item_or_href: Union[epub.EpubItem, str]) -> str:
    """归一化 href 便于与 TOC 匹配：小写、去掉 fragment、统一路径分隔符，最终仅保留文件名。"""
    if hasattr(item_or_href, "get_name"):
        href = item_or_href.get_name() or ""
    else:
        href = str(item_or_href or "")
    href = href.split("#")[0].strip().lower().replace("\\", "/")
    href = re.sub(r"/+", "/", href)
    if href.startswith("../"):
        href = href[3:]
    href = href.strip("/") or href
    return os.path.basename(href)


def _build_toc_title_by_href(book: epub.EpubBook) -> Dict[str, str]:
    """递归展开 book.toc，得到 href（归一化）→ 显示标题 的映射。"""
    result: Dict[str, str] = {}

    def walk(entries: list) -> None:
        for entry in entries:
            if entry is None:
                continue
            if isinstance(entry, epub.Link):
                href = _normalize_href(entry.href)
                title = (entry.title or "").strip()
                if href and title:
                    result[href] = title
            elif isinstance(entry, epub.Section):
                href = (getattr(entry, "href", None) or "").strip()
                if href:
                    result[_normalize_href(href)] = (entry.title or "").strip()
            elif isinstance(entry, (list, tuple)):
                walk(list(entry))

    if hasattr(book, "toc") and book.toc:
        walk(list(book.toc))
    return result


def _normalize_article_title_and_body(item_title: str, full_text: str) -> Tuple[str, str]:
    """规范为明确标题 + 正文：title 不含栏目/路径，content 仅正文。供语义提取无结果时回退使用。"""
    lines = [ln.strip() for ln in full_text.split("\n") if ln.strip()]
    if not lines:
        return (item_title.strip() or "未命名文章", full_text)

    first_line = lines[0]
    title_lower = item_title.lower().strip()
    looks_like_section = (
        ".html" in item_title
        or _is_roundup_or_dynamic_section(title_lower)
        or _is_roundup_or_dynamic_section(first_line.lower())
    )
    if looks_like_section or not item_title.strip():
        raw = re.sub(r"\s+", " ", first_line).strip()
        raw = re.sub(r"feed_\d+/article_\d+/index_\w+\.html", "", raw, flags=re.I)
        raw = re.sub(r"[a-zA-Z0-9_/]+\.html", "", raw)
        match = re.search(r"《([^》]+)》", raw)
        if match:
            final_title = match.group(1).strip()
        else:
            final_title = raw[:200].strip() if raw else "未命名文章"
        if _is_placeholder_title(final_title) and len(lines) > 1:
            raw2 = re.sub(r"\s+", " ", lines[1]).strip()
            raw2 = re.sub(r"feed_\d+/article_\d+/index_\w+\.html", "", raw2, flags=re.I)
            raw2 = re.sub(r"[a-zA-Z0-9_/]+\.html", "", raw2)
            match2 = re.search(r"《([^》]+)》", raw2)
            if match2:
                final_title = match2.group(1).strip()
            else:
                final_title = raw2[:200].strip() if raw2 else "未命名文章"
        if _is_placeholder_title(final_title):
            final_title = "未命名文章"
    else:
        final_title = item_title.strip()
        if _is_placeholder_title(final_title):
            final_title = "未命名文章"

    # 正文：去掉与标题重复或为栏目标题的开头行；若标题来自首行则从第二行开始
    start = 1 if looks_like_section else 0
    body_lines: List[str] = []
    for i, ln in enumerate(lines[start:], start=start):
        ln_lower = ln.lower().strip()
        if ln_lower == final_title.lower().strip():
            continue
        if _is_roundup_or_dynamic_section(ln_lower) and i < 3:
            continue
        body_lines.append(ln)
    # 去掉标题与正文之间的短句（副标题、导语）：从开头连续删除短行，直到遇到第一条足够长的行
    if body_lines:
        for idx, ln in enumerate(body_lines):
            if len(ln.strip()) >= MIN_BODY_LINE_CHARS:
                body_lines = body_lines[idx:]
                break
    body_only = "\n".join(body_lines).strip() if body_lines else full_text

    return (final_title or "未命名文章", body_only)


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    _clean_soup(soup)
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _tag_text(tag) -> str:
    """取标签内文本，多子节点/br 用空格拼接，避免只取到一半。"""
    if tag is None:
        return ""
    return " ".join(tag.stripped_strings) or tag.get_text(separator=" ", strip=True)


def _clean_soup(soup: BeautifulSoup) -> None:
    """清除 HTML 中的非正文干扰元素，防止其污染标题与正文首行。"""
    for tag in soup([
        "script",
        "style",
        "noscript",
        "aside",
        "footer",
        "nav",
        "header",
        "figure",
        "img",
    ]):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(r"(nav|pagination|breadcrumb|header|footer|toc)", re.I)):
        tag.decompose()


def _extract_title_and_body_from_html(
    html: str, item_title: str, toc_title: str | None
) -> Tuple[str, str]:
    """提取标题与正文：优先 TOC → <title> → 语义标签 → 启发式首行回退。"""
    soup = BeautifulSoup(html, "html.parser")
    # 先从 <head> 中提取潜在标题
    head_title = ""
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        head_title = title_tag.string.strip()

    # 清理干扰元素
    _clean_soup(soup)

    final_title = ""
    title_node = None

    # 优先级 1：TOC 中提供的标题
    if toc_title and not _is_placeholder_title(toc_title):
        final_title = toc_title.strip()

    # 优先级 2: 语义化标签 (扩大范围，兼容 Calibre 和常见抓取模板)
    if not final_title:
        for selector in [
            "h1", "h2.title", ".article_title", ".calibre_feed_title",
            "[class*='headline']", "[class*='main-title']",
            "h2", "h3",
        ]:
            node = soup.select_one(selector)
            if node:
                text = _tag_text(node).strip()
                if text and not _is_placeholder_title(text) and text.lower() != "the economist":
                    final_title = text
                    title_node = node
                    break

    # 优先级 3: HTML 原生 <title> 标签 (过滤全局统一名称)
    if not final_title and head_title and not _is_placeholder_title(head_title):
        if head_title.lower() not in ("the economist", "calibre"):
            final_title = head_title

    # 优先级 4：启发式首行回退
    if not final_title:
        full_text = soup.get_text(separator="\n")
        lines = [ln.strip() for ln in full_text.split("\n") if ln.strip()]
        full_text_clean = "\n".join(lines)
        final_title, body_only = _normalize_article_title_and_body(
            item_title, full_text_clean
        )
        return final_title, body_only

    if _is_placeholder_title(final_title):
        final_title = "未命名文章"

    # 若找到了正文内的标题节点，将其移除以避免在正文中重复出现
    if title_node:
        title_node.decompose()

    # 提取并清理正文
    full_text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in full_text.split("\n") if ln.strip()]

    body_lines: List[str] = []
    for ln in lines:
        ln_lower = ln.lower().strip()
        if ln_lower == final_title.lower().strip():
            continue
        if _is_roundup_or_dynamic_section(ln_lower) and len(body_lines) < 3:
            continue
        body_lines.append(ln)

    # 去除开头短句/导语
    if body_lines:
        for idx, ln in enumerate(body_lines):
            if len(ln.strip()) >= MIN_BODY_LINE_CHARS:
                body_lines = body_lines[idx:]
                break

    body_only = "\n".join(body_lines).strip() if body_lines else full_text

    # 清洗标题前缀：RSS/Calibre 常硬编码「标题：」「Title:」等，去掉后还原为纯标题
    if final_title and final_title != "未命名文章":
        final_title = re.sub(
            r"^(?:标题|文章标题|title)\s*[:：\-]?\s*", "", final_title, flags=re.IGNORECASE
        ).strip()
        if not final_title or _is_placeholder_title(final_title):
            final_title = "未命名文章"

    return (final_title[:200] if final_title else "未命名文章", body_only)


def extract_articles_from_epub(path: str) -> List[Article]:
    """从 EPUB 中提取按章节划分的文章列表。"""
    book = epub.read_epub(path)
    toc_title_by_href = _build_toc_title_by_href(book)

    articles: List[Article] = []
    skip_after_twtw = False
    other_skip_titles = ("leaders", "cartoon", "comic", "politics", "business")
    twtw_follow_skip = ("politics", "business", "the weekly cartoon")

    debug_html_dir = None
    if DEBUG_EPUB_HTML:
        debug_html_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".cursor", "epub_html_samples",
        )
        try:
            os.makedirs(debug_html_dir, exist_ok=True)
        except OSError:
            debug_html_dir = None

    article_index = 0
    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        raw_html = item.get_content().decode("utf-8", errors="ignore")
        if DEBUG_EPUB_HTML and debug_html_dir:
            try:
                sample_path = os.path.join(
                    debug_html_dir, f"article_{article_index:03d}.html"
                )
                with open(sample_path, "w", encoding="utf-8") as f:
                    f.write(raw_html[:2000])
            except OSError:
                pass
        article_index += 1

        text = _html_to_text(raw_html)
        if not text or len(text) < 300:
            continue

        title = getattr(item, "title", None) or item.get_name()
        lower_title = title.lower().strip()
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        content_section = (lines[0].lower()[:200] if lines else "")
        content_early = " ".join(ln.lower()[:200] for ln in lines[:5]) if lines else ""

        def _matches_letters(t: str) -> bool:
            return t == "letters" or t.startswith("letters")

        def _is_skip_section(name: str) -> bool:
            return (
                name in twtw_follow_skip
                or "the weekly cartoon" in name
                or any(s in name for s in other_skip_titles)
            )

        if _matches_letters(lower_title) or _matches_letters(content_section):
            continue
        if "the world this week" in lower_title or "the world this week" in content_section:
            skip_after_twtw = True
            continue
        if skip_after_twtw:
            in_twtw_follow = (
                _is_skip_section(lower_title)
                or _is_skip_section(content_section)
                or _is_skip_section(content_early)
            )
            if in_twtw_follow:
                continue
            skip_after_twtw = False
        if _is_skip_section(lower_title) or _is_skip_section(content_section) or _is_skip_section(content_early):
            continue
        if _is_roundup_or_dynamic_section(lower_title) or _is_roundup_or_dynamic_section(content_section) or _is_roundup_or_dynamic_section(content_early):
            continue

        toc_title = toc_title_by_href.get(_normalize_href(item))
        final_title, body_only = _extract_title_and_body_from_html(
            raw_html, title, toc_title
        )

        if final_title == "未命名文章":
            print(f"[DEBUG] 检测到未命名文章 | 文件路径: {item.get_name()}")
            print(f"        正文前80字: {body_only[:80].replace(chr(10), ' ')}")
            print("-" * 50)
            continue

        articles.append(Article(title=final_title, content=body_only))

    return articles

