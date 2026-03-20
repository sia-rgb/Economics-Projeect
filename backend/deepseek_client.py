from __future__ import annotations

import os
import time
import asyncio
import threading
import httpx
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import json

from epub_processing import Article, get_audio_script_skip_rules_text

DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 连接池大小配置
DEEPSEEK_MAX_CONNECTIONS = int(os.getenv("DEEPSEEK_MAX_CONNECTIONS", "10"))
DEEPSEEK_MAX_KEEPALIVE = int(os.getenv("DEEPSEEK_MAX_KEEPALIVE", "30"))
DEEPSEEK_REQUEST_TIMEOUT = float(os.getenv("DEEPSEEK_REQUEST_TIMEOUT", "120.0"))

# 客户端实例缓存（线程局部存储）
_thread_local = threading.local()
_client_cache = {}  # 向后兼容，暂时保留
_client_cache_lock = asyncio.Lock()


@dataclass
class RequestConfig:
    """API请求配置"""
    timeout: float = DEEPSEEK_REQUEST_TIMEOUT
    max_retries: int = 3
    retry_delay: float = 2.0


class DeepSeekClient:
    """DeepSeek API客户端，支持连接复用和批量处理"""

    def __init__(self, api_key: str, base_url: Optional[str] = None, max_connections: int = DEEPSEEK_MAX_CONNECTIONS):
        self.api_key = api_key
        self.base_url = (base_url or DEEPSEEK_API_BASE).rstrip('/')
        self.max_connections = max_connections

        # 创建异步HTTP客户端，启用连接池
        limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=DEEPSEEK_MAX_KEEPALIVE
        )
        timeout = httpx.Timeout(
            connect=30.0,
            read=DEEPSEEK_REQUEST_TIMEOUT,
            write=30.0,
            pool=30.0
        )

        self._client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            http2=True  # 启用HTTP/2以提高性能
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 不自动关闭，客户端是长期存在的
        pass

    async def close(self):
        """关闭HTTP客户端"""
        if hasattr(self, '_client') and self._client:
            await self._client.aclose()

    async def _make_request(
        self,
        messages: List[Dict[str, str]],
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        config: Optional[RequestConfig] = None
    ) -> Dict[str, Any]:
        """执行API请求，支持指数退避重试"""
        config = config or RequestConfig()
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 构建消息列表，如果提供了系统消息则添加
        msg_list = []
        if system_message:
            msg_list.append({"role": "system", "content": system_message})
        msg_list.extend(messages)

        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": msg_list,
            "temperature": temperature,
        }

        last_exc = None
        for attempt in range(config.max_retries):
            try:
                response = await self._client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=config.timeout
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code in [429, 500, 502, 503, 504]:
                    # 可重试的错误
                    if attempt < config.max_retries - 1:
                        delay = config.retry_delay * (2 ** attempt)  # 指数退避
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise DeepSeekError(f"API返回错误状态码 {response.status_code}: {response.text}")
                else:
                    # 不可重试的错误
                    raise DeepSeekError(f"API返回错误状态码 {response.status_code}: {response.text}")

            except (httpx.HTTPError, asyncio.TimeoutError) as e:
                last_exc = e
                if attempt < config.max_retries - 1:
                    delay = config.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise DeepSeekError(f"调用DeepSeek失败: {e}") from e

        if last_exc is not None:
            raise DeepSeekError(f"调用DeepSeek失败: {last_exc}")
        raise DeepSeekError("未知错误")

    async def chat_completion(
        self,
        user_content: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        config: Optional[RequestConfig] = None
    ) -> str:
        """发送单条消息并获取响应"""
        messages = [{"role": "user", "content": user_content}]
        result = await self._make_request(messages, system_message, temperature, config)
        return result["choices"][0]["message"]["content"].strip()

    async def batch_chat_completion(
        self,
        requests: List[Dict[str, Any]],
        config: Optional[RequestConfig] = None
    ) -> List[str]:
        """批量处理多个请求，并发执行"""
        tasks = []
        for req in requests:
            user_content = req.get("user_content", "")
            system_message = req.get("system_message")
            temperature = req.get("temperature", 0.7)
            tasks.append(self.chat_completion(user_content, system_message, temperature, config))

        # 并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果，将异常转换为错误消息
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise DeepSeekError(f"第{i+1}个请求失败: {result}")
            final_results.append(result)

        return final_results


def _run_async_in_sync_context(coro):
    """在同步上下文中运行异步协程"""
    try:
        # 尝试获取当前线程的事件循环
        loop = asyncio.get_event_loop()
        # 检查事件循环是否已关闭
        if loop.is_closed():
            # 事件循环已关闭，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    except RuntimeError as e:
        if "There is no current event loop in thread" in str(e) or "no running event loop" in str(e):
            # 当前线程没有事件循环，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                if not loop.is_closed():
                    loop.close()
        else:
            raise
    except Exception as e:
        # 其他异常，如"Event loop is closed"
        if "Event loop is closed" in str(e) or "loop is closed" in str(e).lower():
            # 创建新的事件循环并重试
            import sys
            print(f"[DEBUG] Event loop was closed, creating new one: {e}", file=sys.stderr)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        raise


class DeepSeekError(Exception):
    """封装 DeepSeek 相关错误。"""


def get_deepseek_client(api_key: str, base_url: Optional[str] = None) -> DeepSeekClient:
    """获取或创建DeepSeekClient实例（线程局部单例模式）"""
    key = (api_key, base_url or DEEPSEEK_API_BASE)

    # 使用线程局部存储，每个线程有自己的客户端实例
    if not hasattr(_thread_local, 'client_cache'):
        _thread_local.client_cache = {}

    if key not in _thread_local.client_cache:
        _thread_local.client_cache[key] = DeepSeekClient(api_key, base_url)

    return _thread_local.client_cache[key]


async def close_all_clients():
    """关闭所有缓存的客户端（包括线程局部存储中的客户端）"""
    # 关闭全局缓存中的客户端（向后兼容）
    for client in _client_cache.values():
        await client.close()
    _client_cache.clear()

    # 关闭当前线程局部存储中的客户端
    if hasattr(_thread_local, 'client_cache'):
        for client in _thread_local.client_cache.values():
            await client.close()
        _thread_local.client_cache.clear()


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
- **标题格式**：第一行必须为「标题：」或「【文章标题】：」+ **文章标题的中文翻译**。若原文标题为英文，须先译为中文再填写，不得保留英文标题。例如「标题：MAGA运动必须面对其外交政策路线上的分歧」，空一行后接正文；不得使用「标题」单独成行或「#### 标题:」等 Markdown 变体。
- **结构**：每篇文章开头为**明确标题**与**正文**两部分；标题与正文之间**不得**出现任何过渡语（如「好的，请听…」「今天我们为您播报…」等），标题后紧接正文。
- **开头**：禁止在标题前或标题与正文之间插入「这是第X篇，共X篇」「中文有声书，第X篇」等说明句或开场白。
- **结尾**：文章结尾**不得**有收束/过渡语（如「这篇文章就为您播报到这里。感谢您的收听。」等），正文结束即结束，直接收尾。
- **分段清晰**：按照原文逻辑分段。
- **标点符号**：多用逗号和句号，少用顿号和分号，确保语流停顿自然。

# Tone
清晰、从容、讲述感强。就像一位知识渊博的朋友坐在副驾驶，把这篇文章一字不落地讲给你听。"""


def _build_audio_script_prompt(article: Article, index: int, total: int) -> str:
    """构建口播逐字稿用的 user prompt：简要说明 + 原标题 + 原文。"""
    content = article.content
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "\n\n[... 原文过长已截断 ...]"
    title_hint = ""
    if article.title and article.title.strip():
        title_hint = f"本文原标题（口播稿首行标题请译为中文后填写）：{article.title.strip()}\n\n"
    return (
        "请将以下英文文章转化为中文口播逐字稿。\n\n"
        f"{title_hint}"
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
    # 使用新的异步客户端，但在同步上下文中运行
    async def _async_call():
        config = RequestConfig(timeout=timeout_seconds)
        client = get_deepseek_client(api_key)
        try:
            # 直接使用_make_request获取原始API响应
            messages = [{"role": "user", "content": user_content}]
            response_data = await client._make_request(
                messages=messages,
                system_message=system_msg,
                temperature=0.7,
                config=config
            )
            # 返回状态码200和JSON字符串
            return (200, json.dumps(response_data))
        except DeepSeekError as e:
            # 从异常中提取状态码信息
            msg = str(e)
            if "API返回错误状态码" in msg:
                # 提取状态码
                import re
                match = re.search(r"API返回错误状态码 (\d+):", msg)
                if match:
                    status_code = int(match.group(1))
                    # 提取错误消息（保持原始格式）
                    error_parts = msg.split(":", 1)
                    error_msg = error_parts[1] if len(error_parts) > 1 else msg
                    return (status_code, error_msg.strip())
            # 其他错误返回500
            return (500, msg)
        except Exception as e:
            return (500, str(e))

    return _run_async_in_sync_context(_async_call())


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


def translate_title_to_chinese(
    title: str,
    api_key: str,
    timeout_seconds: float = 10.0,
) -> str:
    """将英文文章标题翻译为中文，仅返回中文标题。用于口播稿标题兜底。"""
    if not api_key:
        raise DeepSeekError("缺少 DeepSeek API Key。")
    if not title or not title.strip():
        return title or ""
    system_msg = "你是一名专业翻译。请将用户给出的英文文章标题翻译成简洁、准确的中文标题。只输出翻译结果，不要引号、不要解释。"
    user_content = f"请将以下文章标题翻译为中文：\n\n{title.strip()}"
    status_code, resp_text = _do_api_call_with_system(
        system_msg, user_content, api_key, timeout_seconds
    )
    if status_code != 200:
        return title.strip()
    try:
        data = __import__("json").loads(resp_text)
        out = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        return out or title.strip()
    except Exception:
        return title.strip()


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

