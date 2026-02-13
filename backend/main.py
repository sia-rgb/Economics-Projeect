from dotenv import load_dotenv
import os

load_dotenv()

def verify_env_loaded():
    test_env_var = os.getenv("DEEPSEEK_API_KEY")
    if test_env_var:
        print(f"✅ .env 文件加载成功，示例环境变量（部分隐藏）：{test_env_var[:8]}...")
    else:
        print("⚠️  未加载到指定环境变量，请检查 .env 文件是否存在或变量名是否正确")

verify_env_loaded()

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from io import BytesIO
import tempfile
import os
from pathlib import Path

import asyncio
import re
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from epub_processing import extract_articles_from_epub
from deepseek_client import analyze_article_with_deepseek, translate_article_with_deepseek, DeepSeekError
from doc_builder import (
    build_docx_from_analyses,
    build_docx_from_translations,
    _extract_title_from_analysis,
    _extract_article_title,
    _parse_translation,
)


app = FastAPI(title="EPUB Analyst")

# 配置CORS，允许跨域请求
# 生产环境建议指定具体域名，开发环境可以使用 "*"
import os
allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
if allowed_origins == ["*"]:
    # 开发环境或未配置时允许所有来源
    cors_origins = ["*"]
else:
    # 生产环境使用配置的域名列表
    cors_origins = [origin.strip() for origin in allowed_origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_PARALLEL_TASKS = int(os.getenv("MAX_PARALLEL_TASKS", "20"))
_executor = ThreadPoolExecutor(max_workers=MAX_PARALLEL_TASKS)
_semaphore = asyncio.Semaphore(MAX_PARALLEL_TASKS)
_status_lock = asyncio.Lock()
_processing_status: dict[str, dict] = {}  # 存储处理状态
_results_store: dict[str, dict] = {}  # task_id -> { "read_docx": bytes, "listen_docx": bytes, "base_name": str }


def _content_disposition_utf8(filename: str, fallback: str) -> str:
    """RFC 5987: use filename*=UTF-8'' for non-ASCII filenames to avoid Latin-1 encode errors."""
    encoded = quote(filename, safe="")
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'


def _is_cartoon_article(article, analysis: str) -> bool:
    """根据标题或分析内容判断是否为漫画类文章。"""
    title = _extract_title_from_analysis(analysis) or _extract_article_title(article.title)
    title_lower = (title or "").lower()
    analysis_start = (analysis or "")[:500]
    keywords = ["漫画", "cartoon", "comic", "每周漫画", "weekly cartoon"]
    return any(kw in title_lower or kw in analysis_start for kw in keywords)


def _is_cartoon_translation(article, translation: str) -> bool:
    """根据解析出的标题或翻译内容判断是否为漫画类。"""
    title, body, _ = _parse_translation(translation)
    if not title:
        title = _extract_article_title(article.title) or ""
    title_lower = title.lower()
    text_start = (translation or "")[:500]
    keywords = ["漫画", "cartoon", "comic", "每周漫画", "weekly cartoon"]
    return any(kw in title_lower or kw in text_start for kw in keywords)


def _should_exclude_article(article, analysis: str) -> bool:
    """根据引言内容判断是否应该排除该文章。"""
    if not analysis or not analysis.strip():
        return False
    # 提取【引言】段落的内容
    match = re.search(r'【引言】\*?\*?\s*[：:]\s*(.+?)(?=\n\n|【|$)', analysis, re.DOTALL)
    if not match:
        return False
    intro = match.group(1).strip()
    if not intro:
        return False
    # 检查引言中是否包含需要排除的关键词模式
    exclude_patterns = [
        r"概述.*全球政治动态",
        r"综述.*全球金融动态",
        r"概述全球政治动态",
        r"综述全球金融动态",
    ]
    return any(re.search(pattern, intro) for pattern in exclude_patterns)


def _trace(msg: str, clear: bool = False) -> None:
    p = os.path.join(os.path.dirname(__file__), "last_error.txt")
    try:
        with open(p, "w" if clear else "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass


async def _process_single_article(
    article,
    index: int,
    total: int,
    api_key: str,
    task_id: str,
) -> tuple[int, str | None, str | None]:
    """处理单篇文章，返回 (index, analysis, error)。成功时 error 为 None。"""
    async with _semaphore:
        _trace(f"STEP3: calling DeepSeek for article {index}/{total}")
        try:
            loop = asyncio.get_event_loop()
            analysis = await loop.run_in_executor(
                _executor,
                lambda a=article, i=index, t=total, k=api_key: analyze_article_with_deepseek(
                    article=a, index=i, total=t, api_key=k, timeout_seconds=300.0
                ),
            )
            async with _status_lock:
                if task_id in _processing_status:
                    _processing_status[task_id]["current"] = (
                        _processing_status[task_id].get("current", 0) + 1
                    )
            _trace(f"STEP3_DONE: article {index}/{total} completed")
            return (index, analysis, None)
        except DeepSeekError as e:
            _trace(f"STEP_ERR: DeepSeekError article={index} error={str(e)}")
            return (index, None, str(e))


async def _process_single_translation(
    article,
    index: int,
    total: int,
    api_key: str,
    task_id: str,
) -> tuple[int, str | None, str | None]:
    """处理单篇翻译，返回 (index, translation, error)。成功时 error 为 None。"""
    async with _semaphore:
        _trace(f"TRANSLATE: calling DeepSeek for article {index}/{total}")
        try:
            loop = asyncio.get_event_loop()
            translation = await loop.run_in_executor(
                _executor,
                lambda a=article, i=index, t=total, k=api_key: translate_article_with_deepseek(
                    article=a, index=i, total=t, api_key=k, timeout_seconds=180.0
                ),
            )
            async with _status_lock:
                if task_id in _processing_status:
                    _processing_status[task_id]["current"] = (
                        _processing_status[task_id].get("current", 0) + 1
                    )
            _trace(f"TRANSLATE_DONE: article {index}/{total} completed")
            return (index, translation, None)
        except DeepSeekError as e:
            _trace(f"TRANSLATE_ERR: article={index} error={str(e)}")
            return (index, None, str(e))


@app.get("/api/analyze-status/{task_id}")
def get_analyze_status(task_id: str) -> JSONResponse:
    """查询处理状态"""
    status = _processing_status.get(task_id, {"status": "not_found"})
    return JSONResponse(status)


@app.post("/api/analyze-epub")
async def analyze_epub(file: UploadFile = File(...)) -> StreamingResponse:
    import uuid
    task_id = str(uuid.uuid4())
    _processing_status[task_id] = {"status": "processing", "current": 0, "total": 0}
    _trace("STEP0: request started", clear=True)
    if not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="仅支持 EPUB 文件。")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="后端未配置 DEEPSEEK_API_KEY 环境变量，请在服务器上设置后重试。",
        )

    try:
        _trace("STEP1: reading file")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        _trace("STEP2: extracting articles")
        articles = extract_articles_from_epub(tmp_path)
        if not articles:
            raise HTTPException(status_code=400, detail="未能从 EPUB 中解析出有效文章。")

        total = len(articles)
        _processing_status[task_id]["total"] = total

        tasks = [
            _process_single_article(article, idx, total, api_key, task_id)
            for idx, article in enumerate(articles, start=1)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        successful = [(idx, analysis) for idx, analysis, err in results if err is None]
        failed = [(idx, err) for idx, analysis, err in results if err is not None]

        if not successful:
            failed_detail = "; ".join(f"第{i}篇: {e}" for i, e in failed[:5])
            if len(failed) > 5:
                failed_detail += f" ... 共{len(failed)}篇失败"
            _processing_status[task_id] = {"status": "error", "error": failed_detail}
            raise HTTPException(status_code=502, detail=f"所有文章分析失败: {failed_detail}")

        sorted_successful = sorted(successful, key=lambda x: x[0])
        # 过滤掉漫画类文章和特定引言文章
        filtered = [
            (idx, analysis)
            for idx, analysis in sorted_successful
            if not _is_cartoon_article(articles[idx - 1], analysis)
            and not _should_exclude_article(articles[idx - 1], analysis)
        ]
        analyses = [analysis for _, analysis in filtered]
        articles_for_doc = [articles[idx - 1] for idx, _ in filtered]

        if failed:
            _processing_status[task_id]["failed_count"] = len(failed)
            _processing_status[task_id]["failed_indices"] = [i for i, _ in failed]

        _trace("STEP4: building docx")
        _processing_status[task_id]["status"] = "building_docx"
        doc_stream: BytesIO = build_docx_from_analyses(analyses, articles_for_doc)
        _processing_status[task_id]["status"] = "completed"
        base_name = re.sub(r"\.epub$", "", file.filename or "", flags=re.I).strip() or "analysis_result"
        docx_name = f"{base_name}.docx"
        fallback = docx_name if docx_name.isascii() else "analysis_result.docx"
        headers = {"Content-Disposition": _content_disposition_utf8(docx_name, fallback)}
        return StreamingResponse(
            doc_stream,
            media_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml."
                "document"
            ),
            headers=headers,
        )
    except HTTPException:
        raise
    except Exception as e:
        _trace(f"STEP_UNHANDLED: {type(e).__name__}: {e}")
        _processing_status[task_id] = {"status": "error", "error": str(e)}
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}") from e
    finally:
        try:
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


@app.post("/api/translate-epub")
async def translate_epub(file: UploadFile = File(...)) -> StreamingResponse:
    """上传 EPUB，全文翻译后生成 Word 并流式返回。"""
    import uuid
    task_id = str(uuid.uuid4())
    _processing_status[task_id] = {"status": "processing", "current": 0, "total": 0}
    _trace("TRANSLATE_STEP0: request started", clear=True)
    if not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="仅支持 EPUB 文件。")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="后端未配置 DEEPSEEK_API_KEY 环境变量，请在服务器上设置后重试。",
        )

    try:
        _trace("TRANSLATE_STEP1: reading file")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        _trace("TRANSLATE_STEP2: extracting articles")
        articles = extract_articles_from_epub(tmp_path)
        if not articles:
            raise HTTPException(status_code=400, detail="未能从 EPUB 中解析出有效文章。")

        total = len(articles)
        _processing_status[task_id]["total"] = total

        tasks = [
            _process_single_translation(article, idx, total, api_key, task_id)
            for idx, article in enumerate(articles, start=1)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        successful = [(idx, trans) for idx, trans, err in results if err is None]
        failed = [(idx, err) for idx, trans, err in results if err is not None]

        if not successful:
            failed_detail = "; ".join(f"第{i}篇: {e}" for i, e in failed[:5])
            if len(failed) > 5:
                failed_detail += f" ... 共{len(failed)}篇失败"
            _processing_status[task_id] = {"status": "error", "error": failed_detail}
            raise HTTPException(status_code=502, detail=f"所有文章翻译失败: {failed_detail}")

        sorted_successful = sorted(successful, key=lambda x: x[0])
        filtered = [
            (idx, trans)
            for idx, trans in sorted_successful
            if not _is_cartoon_translation(articles[idx - 1], trans)
        ]
        translations = [trans for _, trans in filtered]
        articles_for_doc = [articles[idx - 1] for idx, _ in filtered]

        if failed:
            _processing_status[task_id]["failed_count"] = len(failed)
            _processing_status[task_id]["failed_indices"] = [i for i, _ in failed]

        _trace("TRANSLATE_STEP4: building docx")
        _processing_status[task_id]["status"] = "building_docx"
        doc_stream: BytesIO = build_docx_from_translations(translations, articles_for_doc)
        _processing_status[task_id]["status"] = "completed"
        base_name = re.sub(r"\.epub$", "", file.filename or "", flags=re.I).strip() or "translation_result"
        docx_name = f"{base_name}.docx"
        fallback = docx_name if docx_name.isascii() else "translation_result.docx"
        headers = {"Content-Disposition": _content_disposition_utf8(docx_name, fallback)}
        return StreamingResponse(
            doc_stream,
            media_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            headers=headers,
        )
    except HTTPException:
        raise
    except Exception as e:
        _trace(f"TRANSLATE_UNHANDLED: {type(e).__name__}: {e}")
        _processing_status[task_id] = {"status": "error", "error": str(e)}
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}") from e
    finally:
        try:
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


@app.post("/api/point-me")
async def point_me(file: UploadFile = File(...)) -> JSONResponse:
    """点我：同时跑「看我」（书面翻译）与「听我」（口播稿），结果按 task_id 存，供读我/听我下载。"""
    import uuid
    task_id = str(uuid.uuid4())
    if not file.filename or not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="仅支持 EPUB 文件。")
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="后端未配置 DEEPSEEK_API_KEY 环境变量，请在服务器上设置后重试。",
        )
    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        articles = extract_articles_from_epub(tmp_path)
        if not articles:
            raise HTTPException(status_code=400, detail="未能从 EPUB 中解析出有效文章。")
        total_n = len(articles)
        base_name = re.sub(r"\.epub$", "", file.filename or "", flags=re.I).strip() or "result"
        _processing_status[task_id] = {"status": "processing", "current": 0, "total": 2 * total_n}

        async def flow_listen() -> tuple[list[str], list, list[tuple[int, str]]]:
            tasks = [
                _process_single_article(art, idx, total_n, api_key, task_id)
                for idx, art in enumerate(articles, start=1)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=False)
            successful = [(idx, a) for idx, a, err in results if err is None]
            if not successful:
                raise HTTPException(status_code=502, detail="听我：所有文章口播稿生成失败")
            filtered = [
                (idx, a) for idx, a in sorted(successful, key=lambda x: x[0])
                if a.strip() != "【不生成口播稿】"
                and not _is_cartoon_article(articles[idx - 1], a)
                and not _should_exclude_article(articles[idx - 1], a)
            ]
            analyses = [a for _, a in filtered]
            arts = [articles[i - 1] for i, _ in filtered]
            return (analyses, arts, filtered)

        async def flow_read() -> tuple[list[str], list, list[tuple[int, str]]]:
            tasks = [
                _process_single_translation(art, idx, total_n, api_key, task_id)
                for idx, art in enumerate(articles, start=1)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=False)
            successful = [(idx, t) for idx, t, err in results if err is None]
            if not successful:
                raise HTTPException(status_code=502, detail="看我：所有文章翻译失败")
            filtered = [
                (idx, t) for idx, t in sorted(successful, key=lambda x: x[0])
                if not _is_cartoon_translation(articles[idx - 1], t)
            ]
            translations = [t for _, t in filtered]
            arts = [articles[i - 1] for i, _ in filtered]
            return (translations, arts, filtered)

        (analyses, arts_listen, listen_filtered), (translations, arts_read, read_filtered) = await asyncio.gather(flow_listen(), flow_read())
        read_title_map = {idx: _parse_translation(t)[0] for idx, t in read_filtered}
        titles_for_listen = [read_title_map.get(idx, "") for idx, _ in listen_filtered]
        listen_docx = build_docx_from_analyses(analyses, arts_listen, titles_override=titles_for_listen)
        read_docx = build_docx_from_translations(translations, arts_read)
        listen_docx.seek(0)
        read_docx.seek(0)
        _results_store[task_id] = {
            "read_docx": read_docx.getvalue(),
            "listen_docx": listen_docx.getvalue(),
            "base_name": base_name,
        }
        _processing_status[task_id]["status"] = "completed"
        return JSONResponse({"task_id": task_id, "status": "completed"})
    except HTTPException:
        raise
    except Exception as e:
        _trace(f"POINT_ME_UNHANDLED: {type(e).__name__}: {e}")
        _processing_status[task_id] = {"status": "error", "error": str(e)}
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {e}") from e
    finally:
        try:
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


@app.get("/api/download/read/{task_id}")
def download_read(task_id: str):
    """下载「看我」Word：看+（上传文件名）.docx"""
    if task_id not in _results_store:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    base_name = _results_store[task_id]["base_name"]
    docx_bytes = _results_store[task_id]["read_docx"]
    filename = f"看{base_name}.docx"
    fallback = f"read_{base_name}.docx"
    cd_header = _content_disposition_utf8(filename, fallback)
    return StreamingResponse(
        BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": cd_header},
    )


@app.get("/api/download/listen/{task_id}")
def download_listen(task_id: str):
    """下载「听我」Word：听+（上传文件名）.docx"""
    if task_id not in _results_store:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    base_name = _results_store[task_id]["base_name"]
    docx_bytes = _results_store[task_id]["listen_docx"]
    filename = f"听{base_name}.docx"
    fallback = f"listen_{base_name}.docx"
    cd_header = _content_disposition_utf8(filename, fallback)
    return StreamingResponse(
        BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": cd_header},
    )


@app.get("/health")
def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/api/debug-analyze-first")
async def debug_analyze_first(file: UploadFile = File(...)) -> JSONResponse:
    """上传 EPUB，仅分析第一篇文章，返回结果或错误详情。"""
    if not file.filename.lower().endswith(".epub"):
        return JSONResponse({"ok": False, "error": "仅支持 EPUB 文件"})
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return JSONResponse({"ok": False, "error": "缺少 DEEPSEEK_API_KEY"})
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        articles: List = []
        try:
            articles = extract_articles_from_epub(tmp_path)
            if not articles:
                return JSONResponse({"ok": False, "error": "未能解析出文章", "article_count": 0})
            art = articles[0]
            analysis = analyze_article_with_deepseek(art, 1, len(articles), api_key, timeout_seconds=60.0)
            return JSONResponse({"ok": True, "article_count": len(articles), "first_title": art.title[:80], "content_len": len(art.content), "preview": (analysis or "")[:300]})
        except DeepSeekError as e:
            return JSONResponse({"ok": False, "error": str(e), "article_count": len(articles)})
    finally:
        try:
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


@app.get("/api/debug-deepseek")
@app.get("/debug-deepseek")  # 备用：直接访问后端时用
def debug_deepseek() -> JSONResponse:
    """诊断 DeepSeek 连接，返回实际错误信息。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return JSONResponse({"ok": False, "error": "缺少 DEEPSEEK_API_KEY"})
    try:
        from deepseek_client import analyze_article_with_deepseek
        from epub_processing import Article
        dummy = Article(title="Test", content="Hello, analyze this one sentence.")
        out = analyze_article_with_deepseek(dummy, 1, 1, api_key, timeout_seconds=15.0)
        return JSONResponse({"ok": True, "preview": (out or "")[:200]})
    except DeepSeekError as e:
        return JSONResponse({"ok": False, "error": str(e)})


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


# 静态文件服务（前端构建产物）- 必须在所有API路由之后定义
frontend_dist_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist_path.exists() and (frontend_dist_path / "assets").exists():
    # 挂载静态资源目录（JS/CSS等）
    app.mount("/assets", StaticFiles(directory=str(frontend_dist_path / "assets")), name="assets")

# 服务前端页面（SPA路由支持）- 必须在最后定义
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """服务前端静态文件，支持SPA路由"""
    # API路径已在上面定义，不会到这里
    if full_path.startswith("api"):
        return JSONResponse({"error": "API endpoint not found"}, status_code=404)
    
    frontend_dist_path = Path(__file__).parent.parent / "frontend" / "dist"
    if not frontend_dist_path.exists():
        return JSONResponse({"error": "Frontend not built"}, status_code=404)
    
    # 检查请求的文件是否存在
    file_path = frontend_dist_path / full_path
    if file_path.exists() and file_path.is_file() and file_path.suffix:
        from fastapi.responses import FileResponse
        return FileResponse(str(file_path))
    
    # 对于SPA，所有路由都返回index.html
    index_path = frontend_dist_path / "index.html"
    if index_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(str(index_path))
    
    return JSONResponse({"error": "Frontend not found"}, status_code=404)

