from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

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


def _is_roundup_or_dynamic_section(name: str) -> bool:
    """栏目名是否为需跳过的全球商业/市场/政治动态、漫画、读者来信。"""
    lower = name.lower().strip()
    return any(
        kw in lower or kw in name
        for kw in ROUNDUP_SKIP_KEYWORDS
    )


def _normalize_article_title_and_body(item_title: str, full_text: str) -> Tuple[str, str]:
    """规范为明确标题 + 正文：title 不含栏目/路径，content 仅正文（去掉开头重复标题或栏目标题）。"""
    lines = [ln.strip() for ln in full_text.split("\n") if ln.strip()]
    if not lines:
        return (item_title.strip() or "未命名文章", full_text)

    first_line = lines[0]
    # 若 item 标题像路径或栏目名，用正文首行作为标题
    title_lower = item_title.lower().strip()
    looks_like_section = (
        ".html" in item_title
        or _is_roundup_or_dynamic_section(title_lower)
        or _is_roundup_or_dynamic_section(first_line.lower())
    )
    if looks_like_section or not item_title.strip():
        # 从首行提取标题：去网址、取《》内文等
        raw = re.sub(r"\s+", " ", first_line).strip()
        raw = re.sub(r"feed_\d+/article_\d+/index_\w+\.html", "", raw, flags=re.I)
        raw = re.sub(r"[a-zA-Z0-9_/]+\.html", "", raw)
        match = re.search(r"《([^》]+)》", raw)
        if match:
            final_title = match.group(1).strip()
        else:
            final_title = raw[:200].strip() if raw else "未命名文章"
    else:
        final_title = item_title.strip()

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
    # 去掉常见无用标签
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # 简单清理空行
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def extract_articles_from_epub(path: str) -> List[Article]:
    """从 EPUB 中提取按章节划分的文章列表。"""
    book = epub.read_epub(path)

    articles: List[Article] = []
    skip_after_twtw = False  # 处于「The world this week」之后，需跳过 Politics/Business/The weekly cartoon

    # 其余栏目标题：标题包含即跳过（与顺序无关）
    other_skip_titles = ("leaders", "cartoon", "comic", "politics", "business")

    # 仅在 skip_after_twtw 为 True 时跳过的子栏目（紧接在 The world this week 之后）
    twtw_follow_skip = ("politics", "business", "the weekly cartoon")

    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        raw_html = item.get_content().decode("utf-8", errors="ignore")
        text = _html_to_text(raw_html)
        if not text or len(text) < 300:
            continue

        title = getattr(item, "title", None) or item.get_name()
        lower_title = title.lower().strip()

        # 正文前几行作为栏目名（用于跳过判断）；首行过长时只取前 200 字符
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        content_section = (lines[0].lower()[:200] if lines else "")
        # 前 5 行拼接，便于识别首行之后出现的 "Politics" / "Business" 等栏目标题
        content_early = " ".join(ln.lower()[:200] for ln in lines[:5]) if lines else ""

        def _matches_letters(t: str) -> bool:
            return t == "letters" or t.startswith("letters")

        def _is_skip_section(name: str) -> bool:
            """栏目名是否为需跳过的 Politics/Business/The weekly cartoon 等。"""
            return (
                name in twtw_follow_skip
                or "the weekly cartoon" in name
                or any(s in name for s in other_skip_titles)
            )

        # 1. Letters：直接跳过该条（item 标题或正文首行匹配即跳过）
        if _matches_letters(lower_title) or _matches_letters(content_section):
            continue

        # 2. The world this week：置位并跳过，后续将跳过 Politics/Business/The weekly cartoon
        if "the world this week" in lower_title or "the world this week" in content_section:
            skip_after_twtw = True
            continue

        # 3. 在 twtw 之后且为 Politics/Business/The weekly cartoon 时跳过
        if skip_after_twtw:
            in_twtw_follow = (
                _is_skip_section(lower_title)
                or _is_skip_section(content_section)
                or _is_skip_section(content_early)
            )
            if in_twtw_follow:
                continue
            skip_after_twtw = False

        # 4. 其余栏目（含 Politics、Business）：item 标题或正文前几行包含即跳过
        if _is_skip_section(lower_title) or _is_skip_section(content_section) or _is_skip_section(content_early):
            continue

        # 5. 全球商业/市场/政治动态、漫画、读者来信：标题或正文前几行匹配即跳过
        if _is_roundup_or_dynamic_section(lower_title) or _is_roundup_or_dynamic_section(content_section) or _is_roundup_or_dynamic_section(content_early):
            continue

        final_title, body_only = _normalize_article_title_and_body(title, text)
        articles.append(Article(title=final_title, content=body_only))

    return articles

