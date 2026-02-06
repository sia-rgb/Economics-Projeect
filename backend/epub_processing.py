from __future__ import annotations

from dataclasses import dataclass
from typing import List

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


@dataclass
class Article:
    title: str
    content: str


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

    # 需要跳过的非正式栏目标题（全部转为小写后匹配）
    skip_titles = {
        "the world this week",
        "leaders",
        "the weekly cartoon",
        "letters",
        "politics",
        "business",
        "cartoon",
        "comic",
    }

    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        raw_html = item.get_content().decode("utf-8", errors="ignore")
        text = _html_to_text(raw_html)
        if not text or len(text) < 300:
            # 过滤掉极短内容（如封面、版权页等）
            continue

        # 标题优先取章节标题，其次用文件名兜底
        title = getattr(item, "title", None) or item.get_name()
        lower_title = title.lower()

        # 跳过指定栏目
        if any(skip_title in lower_title for skip_title in skip_titles):
            continue

        articles.append(Article(title=title, content=text))

    return articles

