import React, { useState, useEffect } from "react";

type UploadState = "idle" | "uploading" | "success" | "error";

const MouseIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg viewBox="0 0 64 64" className={className} aria-hidden fill="currentColor">
    <circle cx="20" cy="16" r="8" />
    <circle cx="44" cy="16" r="8" />
    <ellipse cx="32" cy="38" rx="12" ry="20" />
    <path d="M44 50 Q56 42 60 28" stroke="currentColor" strokeWidth="3" fill="none" strokeLinecap="round" />
  </svg>
);

function getEstimatedTotalMs(fileSize: number): number {
  if (fileSize < 2 * 1024 * 1024) return 40_000;
  if (fileSize < 8 * 1024 * 1024) return 90_000;
  return 180_000;
}

export const UploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [estimatedTotalMs, setEstimatedTotalMs] = useState(60_000);
  const handleFileChange: React.ChangeEventHandler<HTMLInputElement> = (event) => {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    setErrorMessage(null);
    setState("idle");
    setBlobUrl(null);
    setProgress(0);
    setStartTime(null);
  };

  useEffect(() => {
    if (state !== "uploading" || startTime === null) return;

    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const baseProgress = Math.min(90, (elapsed / estimatedTotalMs) * 90);
      setProgress((prev) => Math.max(prev, baseProgress));
    }, 100);

    return () => clearInterval(interval);
  }, [state, startTime, estimatedTotalMs]);

  const handleUpload = async () => {
    if (!file) {
      setErrorMessage("请先选择一个 EPUB 文件。");
      return;
    }

    setStartTime(Date.now());
    setEstimatedTotalMs(getEstimatedTotalMs(file.size));
    setProgress(5);
    setState("uploading");
    setErrorMessage(null);
    setBlobUrl(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      // 支持环境变量配置后端地址，开发环境使用代理，生产环境使用完整URL
      const API_BASE = (import.meta.env as any).VITE_API_BASE_URL || '';
      const apiUrl = API_BASE ? `${API_BASE}/api/analyze-epub` : "/api/analyze-epub";
      
      const response = await fetch(apiUrl, {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        let detail = `请求失败 (${response.status})，请稍后重试。`;
        try {
          const text = await response.text();
          const data = text ? JSON.parse(text) : {};
          if (data?.detail) {
            detail =
              typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
          } else if (text) {
            detail = `[${response.status}] ${text.slice(0, 300)}`;
          }
        } catch {
          // keep default detail
        }
        setState("error");
        setErrorMessage(detail);
        setProgress(20);
        return;
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setBlobUrl(url);
      setProgress(90);
      setState("success");
      setTimeout(() => setProgress(100), 150);
    } catch (error) {
      setState("error");
      setErrorMessage((error as Error).message ?? "网络错误，请检查后重试。");
      setProgress(20);
    }
  };

  const handleDownload = () => {
    if (!blobUrl || isDownloading) return;
    setIsDownloading(true);

    const baseName = file?.name ? file.name.replace(/\.epub$/i, "") : "";
    const downloadName = (baseName || "analysis_result") + ".docx";
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = downloadName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setIsDownloading(false);
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
          <div>
            <input
              type="file"
              accept=".epub"
              onChange={handleFileChange}
              className="block w-full text-sm text-slate-700 file:mr-4 file:py-2.5 file:px-5 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-sky-600 file:text-white hover:file:bg-sky-500 cursor-pointer"
            />
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleUpload}
              disabled={!file || isUploading}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-sky-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md shadow-sky-200 hover:bg-sky-500 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              <span>{isUploading ? "正在分析…" : "点我"}</span>
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
            </div>
          )}

          <hr className="my-3 border-slate-100" />

          <div className="flex items-center justify-end">
            <button
              type="button"
              onClick={handleDownload}
              disabled={!blobUrl}
              className="inline-flex items-center justify-center rounded-full border border-sky-300 px-4 py-1.5 text-xs font-medium text-sky-700 bg-white hover:bg-sky-50 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {isDownloading ? "正在下载…" : <>下载 <MouseIcon className="inline-block w-4 h-4 align-middle" /></>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

