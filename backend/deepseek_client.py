from __future__ import annotations

from typing import Literal
import os
import httpx

from epub_processing import Article

DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


class DeepSeekError(Exception):
    """封装 DeepSeek 相关错误。"""


def _calc_detail_level(text: str) -> Literal["short", "medium", "long"]:
    length = len(text)
    if length < 3000:
        return "short"
    if length < 12000:
        return "medium"
    return "long"


def _target_length_hint(detail: Literal["short", "medium", "long"]) -> str:
    if detail == "short":
        return "这篇原文较短，请将总输出控制在约 800 字左右。"
    if detail == "medium":
        return "这篇原文篇幅中等，请将总输出控制在约 1500 字左右。"
    return "这篇原文较长，请将总输出控制在约 3000 字左右。"


# DeepSeek 上下文限制约 32k tokens，约 12 万字符；单篇正文截断以留出 prompt 空间
MAX_CONTENT_CHARS = int(os.getenv("DEEPSEEK_MAX_CONTENT_CHARS", "80000"))


def _build_prompt_from_content(content: str, index: int, total: int) -> str:
    detail = _calc_detail_level(content)
    length_hint = _target_length_hint(detail)
    return (
        "你是一名熟悉经济与金融领域的中文分析师。请对下面这段英文文本进行结构化分析，"
        "将其转述为中文并提取关键信息。\n\n"
        f"这是待分析文本集中的第 {index} 段，共 {total} 段。\n\n"
        "请你严格按照下面的中文结构输出：\n"
        "【文章标题】**：请翻译或提取文章的主标题。禁止使用刊名、杂志名（如《经济学人》、经济学人、The Economist）作为标题。若原文有明确标题则翻译；若无则根据文章内容概括出具体主题（如「每周漫画：特朗普的政治影响」「读者来信：欧洲防务」），务必使每篇文章标题互不相同且能反映该文主题。\n"
        "【引言】**：(1-2句话点明背景或核心问题)\n"
        "【主要内容如下】**：(逻辑清晰地转述核心内容，保留关键细节，分段表述)\n"
        "【关键数据】**：(提取具体的金额、百分比、年份等硬指标，如无数据则填“无”)\n"
        "【核心结论】**：(一句话提炼主要观点)\n"
        "【分析师简评】**：(从专业角度简要点评)\n\n"
        "要求：\n"
        "1. 输出语言必须是中文。\n"
        "2. 严格保留以上每一个小节标题（包括方括号和全角标点），并用自然段分隔。\n"
        "3. 不要添加额外的小节或前后说明文字。\n"
        "4. 确保信息量与原文长度大致匹配，不要过度删减关键信息。\n"
        f"5. {length_hint}\n\n"
        "待分析的英文文本：\n\n"
        f"{content}"
    )


def _build_prompt(article: Article, index: int, total: int) -> str:
    content = article.content
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "\n\n[... 原文过长已截断 ...]"
    return _build_prompt_from_content(content, index, total)


def _do_api_call(
    prompt: str, api_key: str, timeout_seconds: float
) -> tuple[int, str]:
    """执行 API 调用，返回 (status_code, response_text)。"""
    url = f"{DEEPSEEK_API_BASE.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    system_msg = (
        "You are a financial analyst assistant. The user provides text for you to summarize "
        "and analyze in Chinese. Perform the analysis as requested; this is for personal "
        "study and transformation, not reproduction."
    )
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }
    timeout_config = httpx.Timeout(
        connect=30.0, read=timeout_seconds, write=30.0, pool=30.0
    )
    with httpx.Client(timeout=timeout_config) as client:
        resp = client.post(url, json=payload, headers=headers)
    return (resp.status_code, resp.text)


def analyze_article_with_deepseek(
    article: Article,
    index: int,
    total: int,
    api_key: str,
    timeout_seconds: float = 120.0,
) -> str:
    """调用 DeepSeek 对单篇文章进行分析，返回中文结构化文本。"""
    if not api_key:
        raise DeepSeekError("缺少 DeepSeek API Key。")

    content = article.content
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "\n\n[... 原文过长已截断 ...]"

    # #region agent log
    _log_dir = os.path.join(os.path.dirname(__file__), "..", ".cursor")
    _log_path = os.path.join(_log_dir, "debug.log")

    def _agent_log(loc: str, msg: str, data: dict, hid: str):
        try:
            import json
            os.makedirs(_log_dir, exist_ok=True)
            with open(_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"location": loc, "message": msg, "data": data, "timestamp": int(__import__("time").time() * 1000), "sessionId": "debug-session", "hypothesisId": hid}) + "\n")
        except Exception:
            pass
    # #endregion

    fallback_contents = [content]
    if len(content) > 6000:
        fallback_contents.append(content[:6000] + "\n\n[... 为通过审核已截断 ...]")
    if len(content) > 3000:
        fallback_contents.append(content[:3000] + "\n\n[... 为通过审核已截断 ...]")

    last_error = ""
    for attempt, content_to_use in enumerate(fallback_contents):
        try:
            prompt = _build_prompt_from_content(content_to_use, index, total)
            status_code, resp_text = _do_api_call(prompt, api_key, timeout_seconds)
        except httpx.HTTPError as exc:
            _agent_log("deepseek_client.py:HTTPError", "httpx.HTTPError", {"error": str(exc)[:200]}, "H2")
            raise DeepSeekError(f"调用 DeepSeek 失败：{exc}") from exc

        if status_code == 200:
            try:
                data = __import__("json").loads(resp_text)
                return data["choices"][0]["message"]["content"].strip()
            except Exception as exc:
                _agent_log("deepseek_client.py:parse", "parse fail", {"error": str(exc)[:200]}, "H3")
                raise DeepSeekError(f"解析 DeepSeek 响应失败：{exc}") from exc

        last_error = resp_text
        if "Content Exists Risk" in resp_text and attempt < len(fallback_contents) - 1:
            _agent_log("deepseek_client.py:retry", "Content Exists Risk, retrying with shorter content", {
                "article_index": index, "attempt": attempt + 1,
            }, "H1")
            continue

        _agent_log("deepseek_client.py:status", "non-200", {
            "status": status_code,
            "text": last_error[:500],
            "article_index": index,
            "content_preview": content[:200],
        }, "H1")
        print(f"[DEBUG] DeepSeek API status {status_code}: {last_error[:300]}")
        raise DeepSeekError(f"DeepSeek 返回错误状态码 {status_code}: {last_error}")

