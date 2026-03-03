import React, { useState, useEffect, useRef } from "react";

type UploadState = "idle" | "uploading" | "success" | "error";

const MouseIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg viewBox="0 0 64 64" className={className} aria-hidden fill="currentColor">
    <circle cx="20" cy="16" r="8" />
    <circle cx="44" cy="16" r="8" />
    <ellipse cx="32" cy="38" rx="12" ry="20" />
    <path d="M44 50 Q56 42 60 28" stroke="currentColor" strokeWidth="3" fill="none" strokeLinecap="round" />
  </svg>
);

const POLL_INTERVAL_MS = 3000;

function getEstimatedTotalMs(fileSize: number): number {
  if (fileSize < 2 * 1024 * 1024) return 120_000;
  if (fileSize < 8 * 1024 * 1024) return 240_000;
  return 360_000;
}

export const UploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [resultType, setResultType] = useState<"listen" | "read" | null>(null);
  const [pendingAction, setPendingAction] = useState<"listen" | "read" | null>(null);
  const [progress, setProgress] = useState(0);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [estimatedTotalMs, setEstimatedTotalMs] = useState(60_000);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const handleFileChange: React.ChangeEventHandler<HTMLInputElement> = (event) => {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    setErrorMessage(null);
    setState("idle");
    setTaskId(null);
    setResultType(null);
    setPendingAction(null);
    setProgress(0);
    setStartTime(null);
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (state !== "uploading" || startTime === null) return;
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const ratio = Math.min(1, elapsed / estimatedTotalMs);
      const estimatedProgress = Math.min(90, 90 * Math.pow(ratio, 0.7));
      setProgress((prev) => Math.max(prev, estimatedProgress));
    }, 100);
    return () => clearInterval(interval);
  }, [state, startTime, estimatedTotalMs]);

  const API_BASE = (import.meta.env as any).VITE_API_BASE_URL || "";

  const pollStatus = (id: string) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    const check = async () => {
      try {
        const url = API_BASE ? `${API_BASE}/api/analyze-status/${id}` : `/api/analyze-status/${id}`;
        const res = await fetch(url);
        const statusData = await res.json();
        if (statusData.status === "processing" || statusData.status === "building_docx") {
          const total = statusData.total ?? 0;
          const current = statusData.current ?? 0;
          if (total > 0) {
            const realProgress = statusData.status === "building_docx"
              ? 95
              : Math.floor((current / total) * 90);
            setProgress(realProgress);
          }
        } else if (statusData.status === "completed") {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setProgress(100);
          setState("success");
          setPendingAction(null);
        } else if (statusData.status === "error") {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setState("error");
          setErrorMessage(statusData.error ?? "处理失败");
          setPendingAction(null);
        } else if (statusData.status === "not_found") {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setState("error");
          setErrorMessage("任务不存在或已过期");
          setPendingAction(null);
        }
      } catch {
        // Network error: ignore, next poll will retry
      }
    };
    check();
    pollIntervalRef.current = setInterval(check, POLL_INTERVAL_MS);
  };

  const runPipeline = async (endpoint: "listen-me" | "read-me", type: "listen" | "read") => {
    if (!file) {
      setErrorMessage("请先选择一个 EPUB 文件。");
      return;
    }
    setProgress(5);
    setState("uploading");
    setErrorMessage(null);
    setTaskId(null);
    setResultType(null);
    setPendingAction(type);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const apiUrl = API_BASE ? `${API_BASE}/api/${endpoint}` : `/api/${endpoint}`;
      const response = await fetch(apiUrl, { method: "POST", body: formData });
      const data = await response.json();

      if (!response.ok || !data.task_id) {
        const detail = data?.detail
          ? typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail)
          : `请求失败 (${response.status})，请稍后重试。`;
        setState("error");
        setErrorMessage(detail);
        setPendingAction(null);
        return;
      }

      setTaskId(data.task_id);
      setResultType(type);
      setStartTime(Date.now());
      setEstimatedTotalMs(getEstimatedTotalMs(file.size));
      pollStatus(data.task_id);
    } catch (error) {
      setState("error");
      setErrorMessage((error as Error).message ?? "网络错误，请检查后重试。");
      setPendingAction(null);
    }
  };

  const handleListenMe = () => runPipeline("listen-me", "listen");
  const handleReadMe = () => runPipeline("read-me", "read");

  const baseName = file?.name ? file.name.replace(/\.epub$/i, "").trim() || "result" : "result";

  const triggerFileDownload = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.rel = "noopener noreferrer";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleDownloadRead = async () => {
    if (!taskId) {
      setErrorMessage("请先选择「听我」或「读我」并等待处理完成后再下载。");
      return;
    }
    if (isDownloading) return;
    const url = API_BASE ? `${API_BASE}/api/download/read/${taskId}` : `/api/download/read/${taskId}`;
    setIsDownloading(true);
    setErrorMessage(null);
    try {
      const res = await fetch(url);
      if (!res.ok) {
        if (res.status === 404) {
          setErrorMessage("任务不存在或已过期，请重新选择听我/读我后再下载。");
          return;
        }
        setErrorMessage(`下载失败 (${res.status})，请稍后重试。`);
        return;
      }
      const blob = await res.blob();
      triggerFileDownload(blob, `看${baseName}.docx`);
    } catch {
      setErrorMessage("无法连接下载服务，请确认后端已启动或稍后重试。");
    } finally {
      setIsDownloading(false);
    }
  };

  const handleDownloadListen = async () => {
    if (!taskId) {
      setErrorMessage("请先选择「听我」或「读我」并等待处理完成后再下载。");
      return;
    }
    if (isDownloading) return;
    const url = API_BASE ? `${API_BASE}/api/download/listen/${taskId}` : `/api/download/listen/${taskId}`;
    setIsDownloading(true);
    setErrorMessage(null);
    try {
      const res = await fetch(url);
      if (!res.ok) {
        if (res.status === 404) {
          setErrorMessage("任务不存在或已过期，请重新选择听我/读我后再下载。");
          return;
        }
        setErrorMessage(`下载失败 (${res.status})，请稍后重试。`);
        return;
      }
      const blob = await res.blob();
      triggerFileDownload(blob, `听${baseName}.docx`);
    } catch {
      setErrorMessage("无法连接下载服务，请确认后端已启动或稍后重试。");
    } finally {
      setIsDownloading(false);
    }
  };

  const handleDownload = async () => {
    if (resultType === "listen") await handleDownloadListen();
    else if (resultType === "read") await handleDownloadRead();
  };

  const isUploading = state === "uploading";

  return (
    <div className="relative min-h-screen flex items-center justify-center px-4">
      {/* 背景柔和蓝色渐变波纹 */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-sky-50 via-white to-sky-100" />
      <div className="pointer-events-none absolute -bottom-40 -left-24 h-80 w-80 rounded-full bg-sky-200/40 blur-3xl" />
      <div className="pointer-events-none absolute -top-40 -right-10 h-72 w-72 rounded-full bg-sky-300/40 blur-3xl" />

      <span
        className="fixed bottom-4 right-4 text-[20px] text-slate-400 z-20"
        style={{ fontFamily: "Microsoft YaHei, 微软雅黑, sans-serif" }}
      >
        Copyright@MOI
      </span>

      <div className="relative z-10 w-full max-w-3xl">
        <div className="text-center mb-10 flex items-center justify-center gap-3">
          <MouseIcon className="w-12 h-12 md:w-14 md:h-14 text-sky-500 opacity-90" />
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight text-sky-600 drop-shadow-sm">
            TX Economics
          </h1>
          <MouseIcon className="w-12 h-12 md:w-14 md:h-14 text-sky-500 opacity-90" />
        </div>

        <div className="rounded-3xl bg-white/90 backdrop-blur-lg shadow-xl border border-sky-100 px-6 py-7 md:px-10 md:py-9 flex flex-col gap-6">
          <div className="relative flex items-center gap-3 min-h-[2.75rem]">
            <input
              type="file"
              accept=".epub"
              onChange={handleFileChange}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
            />
            <span className="pointer-events-none rounded-full bg-sky-600 px-5 py-2.5 text-xs font-semibold text-white shrink-0">
              选我
            </span>
            <span className="pointer-events-none text-sm text-slate-700 truncate">
              {file?.name ?? "未选择文件"}
            </span>
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleListenMe}
              disabled={!file || isUploading}
              className="inline-flex items-center justify-center gap-2 rounded-full border border-sky-800 bg-white px-6 py-2.5 text-sm font-semibold text-sky-800 hover:bg-sky-50 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              <span>{isUploading && pendingAction === "listen" ? "正在处理…" : "听我"}</span>
            </button>
            <button
              type="button"
              onClick={handleReadMe}
              disabled={!file || isUploading}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-sky-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md shadow-sky-200 hover:bg-sky-500 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              <span>{isUploading && pendingAction === "read" ? "正在处理…" : "读我"}</span>
            </button>
          </div>

          <div className="text-sm">
            {state === "idle" && (
              <div className="border-l-4 border-slate-200 pl-3 text-slate-500">
                你瞅啥，还不上传
              </div>
            )}
            {state === "uploading" && (
              <div className="border-l-4 border-sky-300 pl-3 text-sky-600">
                Don't push, Thank you 🍺
              </div>
            )}
            {state === "success" && (
              <div className="border-l-4 border-emerald-300 pl-3 text-emerald-600">
                搞定，别崇拜姐，姐就是传说
              </div>
            )}
            {state === "error" && (
              <div className="border-l-4 border-red-300 pl-3 text-red-600">
                {errorMessage ?? "处理过程中出现错误。"}
              </div>
            )}
            {errorMessage && state !== "error" && (
              <div className="border-l-4 border-amber-300 pl-3 text-amber-700">
                {errorMessage}
              </div>
            )}
          </div>

          {state !== "idle" && (
            <div>
              <div className="mt-2 h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                <div
                  className={
                    "h-full rounded-full transition-all duration-500 " +
                    (state === "error"
                      ? "bg-red-400"
                      : state === "success"
                        ? "bg-emerald-400"
                        : "bg-sky-400")
                  }
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="mt-1 text-[10px] text-right text-slate-400">
                {state === "uploading" && "正在处理中…"}
                {state === "success" && "记得打钱 💰"}
                {state === "error" && "处理失败"}
              </div>
              {state === "success" && taskId && (
                <div className="mt-3 flex justify-end">
                  <button
                    type="button"
                    onClick={handleDownload}
                    disabled={isDownloading}
                    className="inline-flex items-center justify-center gap-2 rounded-full bg-sky-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md shadow-sky-200 hover:bg-sky-500 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
                  >
                    <span>{isDownloading ? "正在下载…" : "下载"}</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

