from __future__ import annotations

import os
import time
import httpx

from epub_processing import Article, get_audio_script_skip_rules_text

DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


class DeepSeekError(Exception):
    """封装 DeepSeek 相关错误。"""


# DeepSeek 上下文限制约 32k tokens，约 12 万字符；单篇正文截断以留出 prompt 空间
MAX_CONTENT_CHARS = int(os.getenv("DEEPSEEK_MAX_CONTENT_CHARS", "80000"))

# 口播逐字稿用 system message（听我）；跳过规则由 epub_processing 单一数据源提供
AUDIO_SCRIPT_SYSTEM_MESSAGE = f"""# Role
你是一位专业的《经济学人》中文版有声书播音员。你的听众正在通勤路上，他们无法看屏幕，只能通过耳朵获取信息。你的任务是将英文原文转化为一份**高质量的中文口播逐字稿**。

# Goal
请将提供的英文文章完整地转化为中文口语稿。
**核心要求是：内容上完全忠实于原文，不删减任何细节；形式上完全服务于耳朵，极度从容、易懂。**

{get_audio_script_skip_rules_text()}

# Critical Rules for Audio Script (听觉化改编原则)

1. **信息零损失 (Zero Information Loss)**：
   - **严禁删减**：这不仅是摘要，而是全文通读。原文的每一个论点、案例、数据、人名、背景描写都必须保留。
   - **数据处理**：保留精确数据，但在播报时要符合中文读数习惯。例如原文 "24.5%"，口语稿可写作 "百分之二十四点五"。

2. **长难句"碎尸万段" (Deconstruct Complex Sentences)**：
   - 听觉是线性的，无法回看。**严禁**使用定语过长的倒装句（如"那个由...导致了...的...政策"）。
   - **必须拆句**：将复杂的从句拆解为多个简单的短句。
   - *Bad (书面)*："受通胀高企和供应链断裂双重打击的全球市场今日表现疲软。"
   - *Good (口语)*："全球市场今天的表现很疲软。这主要是受到了两个因素的打击：一个是居高不下的通胀，另一个是供应链的断裂。"

3. **拒绝"翻译腔"与生僻书面语 (No Translationese)**：
   - 能够口说的词，就不要用书面词。
   - 把"**基于**"改为"**根据**"或"**靠**"。
   - 把"**旨在**"改为"**目的是**"。
   - 把"**未曾**"改为"**没有**"。
   - 把"**其**"改为"**它的**"或"**他的**"。
   - 确保听众不需要在脑子里"转译"一遍就能听懂。

4. **显性逻辑连接 (Explicit Signposting)**：
   - 在段落和观点切换时，加入明显的口语连接词，帮助听众跟上节奏。
   - 使用："首先"、"比如说"、"这就意味着"、"换句话说"、"值得注意的是"。

# Output Format
- **标题格式**：第一行必须为「标题：」+ 文章标题（例如「标题：MAGA运动必须面对其外交政策路线上的分歧」），空一行后接正文；不得使用「标题」单独成行或「#### 标题:」等 Markdown 变体。
- **结构**：每篇文章开头为**明确标题**与**正文**两部分；标题与正文之间**不得**出现任何过渡语（如「好的，请听…」「今天我们为您播报…」等），标题后紧接正文。
- **开头**：禁止在标题前或标题与正文之间插入「这是第X篇，共X篇」「中文有声书，第X篇」等说明句或开场白。
- **结尾**：文章结尾**不得**有收束/过渡语（如「这篇文章就为您播报到这里。感谢您的收听。」等），正文结束即结束，直接收尾。
- **分段清晰**：按照原文逻辑分段。
- **标点符号**：多用逗号和句号，少用顿号和分号，确保语流停顿自然。

# Tone
清晰、从容、讲述感强。就像一位知识渊博的朋友坐在副驾驶，把这篇文章一字不落地讲给你听。"""


def _build_audio_script_prompt(article: Article, index: int, total: int) -> str:
    """构建口播逐字稿用的 user prompt：简要说明 + 原文。"""
    content = article.content
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "\n\n[... 原文过长已截断 ...]"
    return (
        "请将以下英文文章转化为中文口播逐字稿。\n\n"
        "待转化的英文原文：\n\n"
        f"{content}"
    )


# 全文翻译用 system message（信达雅、输出格式、语气）
TRANSLATE_SYSTEM_MESSAGE = """# Role
你是一位精通中英双语的资深主笔，曾服务于《经济学人》中文版或《纽约时报》中文网。你擅长将复杂的英文政经深度报道翻译成符合中文母语者阅读习惯的高质量文章。

# Goal
请将用户提供的英文文章翻译成中文。你的翻译需要达到"信、达、雅"的标准。

# Constraints & Workflow
1. **信 (Faithfulness)**：
   - 准确理解原文的核心观点、逻辑推导和隐含态度（如讽刺、幽默）。
   - 保留所有关键数据、年份和人名（人名首次出现需附英文原名）。
   - 不要遗漏原文的任何一个论点。

2. **达 (Expressiveness)**：
   - 彻底摆脱"翻译腔"。不要逐字对译，而要按中文的逻辑重组句子。
   - 长难句需拆分为符合汉语习惯的短句。
   - 确保段落之间过渡自然，逻辑连贯。

3. **雅 (Elegance)**：
   - 用词需考究、精准。对于经济学术语，使用专业的中文定译。
   - 在不改变原意的前提下，适当使用四字成语或优美的修辞，提升文本的文学性。
   - 保持原文的语体风格（如果是严肃分析，译文要庄重；如果是轻松随笔，译文要活泼）。

# Output Format
- 标题：【重拟一个吸引人的中文标题，既要信实又要抓眼球】
- 正文：全译文本，分段排版，保持阅读呼吸感。 
译者注：如果在翻译过程中遇到特殊的文化梗或背景知识，请在文末用"译者注"简要解释。

# Tone
客观、冷静、专业，兼具深度与可读性。"""


def _build_translate_prompt(article: Article, index: int, total: int) -> str:
    """构建全文翻译用的 user prompt：简要说明 + 原文。"""
    content = article.content
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "\n\n[... 原文过长已截断 ...]"
    return (
        "请将以下英文文章翻译成中文。\n\n"
        "请严格按照 Output Format 输出：标题、正文、译者注（如有）。\n\n"
        "待翻译的英文原文：\n\n"
        f"{content}"
    )


def _do_api_call_with_system(
    system_msg: str,
    user_content: str,
    api_key: str,
    timeout_seconds: float,
) -> tuple[int, str]:
    """执行 API 调用，使用指定的 system message，返回 (status_code, response_text)。连接中断时自动重试。"""
    url = f"{DEEPSEEK_API_BASE.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.7,
    }
    timeout_config = httpx.Timeout(
        connect=30.0, read=timeout_seconds, write=30.0, pool=30.0
    )
    last_exc = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=timeout_config) as client:
                resp = client.post(url, json=payload, headers=headers)
                body = resp.text
            return (resp.status_code, body)
        except httpx.HTTPError as e:
            last_exc = e
            msg = str(e).lower()
            if attempt < 2 and ("chunked" in msg or "peer closed" in msg or "connection" in msg or "incomplete" in msg):
                time.sleep(2.0 * (attempt + 1))
                continue
            raise DeepSeekError(f"调用 DeepSeek 失败：{e}") from e
    if last_exc is not None:
        raise DeepSeekError(f"调用 DeepSeek 失败：{last_exc}") from last_exc
    return (500, "")


def _do_api_call(
    prompt: str, api_key: str, timeout_seconds: float
) -> tuple[int, str]:
    """执行 API 调用，返回 (status_code, response_text)。"""
    system_msg = (
        "You are a financial analyst assistant. The user provides text for you to summarize "
        "and analyze in Chinese. Perform the analysis as requested; this is for personal "
        "study and transformation, not reproduction."
    )
    return _do_api_call_with_system(system_msg, prompt, api_key, timeout_seconds)


def analyze_article_with_deepseek(
    article: Article,
    index: int,
    total: int,
    api_key: str,
    timeout_seconds: float = 120.0,
) -> str:
    """调用 DeepSeek 对单篇文章生成口播逐字稿（听我），返回中文口播稿文本。"""
    if not api_key:
        raise DeepSeekError("缺少 DeepSeek API Key。")

    content = article.content
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "\n\n[... 原文过长已截断 ...]"

    fallback_articles = [
        Article(title=article.title, content=content),
    ]
    if len(content) > 6000:
        fallback_articles.append(Article(title=article.title, content=content[:6000] + "\n\n[... 为通过审核已截断 ...]"))
    if len(content) > 3000:
        fallback_articles.append(Article(title=article.title, content=content[:3000] + "\n\n[... 为通过审核已截断 ...]"))

    last_error = ""
    for attempt, art in enumerate(fallback_articles):
        try:
            user_prompt = _build_audio_script_prompt(art, index, total)
            status_code, resp_text = _do_api_call_with_system(
                AUDIO_SCRIPT_SYSTEM_MESSAGE, user_prompt, api_key, timeout_seconds
            )
        except httpx.HTTPError as exc:
            raise DeepSeekError(f"调用 DeepSeek 失败：{exc}") from exc

        if status_code == 200:
            try:
                data = __import__("json").loads(resp_text)
                return data["choices"][0]["message"]["content"].strip()
            except Exception as exc:
                raise DeepSeekError(f"解析 DeepSeek 响应失败：{exc}") from exc

        last_error = resp_text
        if "Content Exists Risk" in resp_text and attempt < len(fallback_articles) - 1:
            continue

        print(f"[DEBUG] DeepSeek API status {status_code}: {last_error[:300]}")
        raise DeepSeekError(f"DeepSeek 返回错误状态码 {status_code}: {last_error}")


def translate_article_with_deepseek(
    article: Article,
    index: int,
    total: int,
    api_key: str,
    timeout_seconds: float = 180.0,
) -> str:
    """调用 DeepSeek 对单篇文章进行全文翻译，返回含标题、正文、译者注的中文文本。"""
    if not api_key:
        raise DeepSeekError("缺少 DeepSeek API Key。")

    user_prompt = _build_translate_prompt(article, index, total)
    status_code, resp_text = _do_api_call_with_system(
        TRANSLATE_SYSTEM_MESSAGE, user_prompt, api_key, timeout_seconds
    )

    if status_code != 200:
        raise DeepSeekError(f"DeepSeek 返回错误状态码 {status_code}: {resp_text}")

    try:
        data = __import__("json").loads(resp_text)
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise DeepSeekError(f"解析 DeepSeek 响应失败：{exc}") from exc

