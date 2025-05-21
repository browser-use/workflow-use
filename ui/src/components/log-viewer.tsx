import React, { useState, useEffect, useRef } from "react";
import { LogViewerProps } from "../types/log-viewer.types";

const LogViewer: React.FC<LogViewerProps> = ({
  taskId,
  initialPosition,
  onStatusChange,
  onError,
  onCancel,
  onClose,
}) => {
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [position, setPosition] = useState<number>(initialPosition);
  const [status, setStatus] = useState<string>("running");
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState<boolean>(true);

  const logContainerRef = useRef<HTMLDivElement>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  useEffect(() => {
    return () => {
      setPolling(false);
    };
  }, []);

  useEffect(() => {
    if (!taskId) return;

    const pollLogs = async () => {
      try {
        const response = await fetch(
          `http://127.0.0.1:8000/api/workflows/logs/${taskId}?position=${position}`
        );

        if (!response.ok) {
          throw new Error(`Error fetching logs: ${response.status}`);
        }

        const data = await response.json();

        if (data.logs && data.logs.length > 0) {
          setLogs((prevLogs) => [...prevLogs, ...data.logs]);
        }

        setPosition(data.log_position);

        if (data.status && data.status !== status) {
          setStatus(data.status);
          onStatusChange?.(data.status);

          if (data.status === "failed" && data.error) {
            setError(data.error);
            onError?.(data.error);
          }
        }
      } catch (err) {
        console.error("Error polling logs:", err);
      }
    };

    pollLogs();

    pollingIntervalRef.current = setInterval(() => {
      if (polling) {
        pollLogs();
      }
    }, 2000);

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [taskId, position, status, polling, onStatusChange, onError]);

  const cancelWorkflow = async () => {
    if (!taskId || isCancelling || status !== "running") return;

    setIsCancelling(true);

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/workflows/tasks/${taskId}/cancel`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      const data = await response.json();

      if (response.ok && data.success) {
        // The status will be updated through the polling mechanism
        if (onCancel) {
          onCancel();
        }
      } else {
        console.error(
          "Failed to cancel workflow:",
          data.message || "Unknown error"
        );
      }
    } catch (err) {
      console.error("Error cancelling workflow:", err);
    } finally {
      setIsCancelling(false);
    }
  };

  const downloadLogs = () => {
    if (logs.length === 0) return;

    const textContent = logs.join("");

    const blob = new Blob([textContent], { type: "text/plain" });

    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = taskId
      ? `workflow-logs-${taskId}.txt`
      : "workflow-logs.txt";

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
  };

  const formatLog = (log: string, index: number) => {
    const timestampMatch = log.match(/^\[(.*?)\]/);

    if (timestampMatch) {
      const timestamp = timestampMatch[0];
      const message = log.substring(timestamp.length);

      return (
        <div key={index} className="log-line">
          <span className="log-timestamp">{timestamp}</span>
          <span className="log-message">{message}</span>
        </div>
      );
    }

    return (
      <div key={index} className="log-line">
        {log}
      </div>
    );
  };

  return (
    <div className="w-full h-[350px] flex flex-col border border-[#ddd] rounded-md overflow-hidden my-4 bg-[#f8f9fa] font-mono">
      <div className="flex justify-between p-2 bg-[#f0f2f5] border-b border-[#ddd]">
        <div className="font-semibold text-[#333]">Workflow Execution Logs</div>
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-2">
            {status === "running" && (
              <button
                className={`flex items-center gap-1 py-1 px-2 bg-[#fff2f0] border border-[#ffccc7] rounded text-xs cursor-pointer text-[#ff4d4f] transition-all hover:bg-[#fff1f0] hover:border-[#ffa39e] ${
                  isCancelling ? "opacity-60 cursor-not-allowed" : ""
                }`}
                onClick={cancelWorkflow}
                disabled={isCancelling}
                title="Cancel workflow execution"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="w-3.5 h-3.5"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="15" y1="9" x2="9" y2="15" />
                  <line x1="9" y1="9" x2="15" y2="15" />
                </svg>
                {isCancelling ? "Cancelling..." : "Cancel"}
              </button>
            )}
            {logs.length > 0 && (
              <button
                className="flex items-center gap-1 py-1 px-2 bg-[#f5f5f5] border border-[#ddd] rounded text-xs cursor-pointer text-[#333] transition-all hover:bg-[#e6e6e6] hover:border-[#ccc]"
                onClick={downloadLogs}
                title="Download logs as text file"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="w-3.5 h-3.5"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Download
              </button>
            )}
          </div>
          <div
            className={`py-0.5 px-2 rounded text-xs font-medium ${
              status === "running"
                ? "bg-[#e6f7ff] text-[#1890ff] border border-[#91d5ff]"
                : status === "completed"
                ? "bg-[#f6ffed] text-[#52c41a] border border-[#b7eb8f]"
                : status === "cancelling"
                ? "bg-[#fff2f0] text-orange border border-[#ffccc7]"
                : status === "cancelled"
                ? "bg-[#fff2f0] text-[#ff4d4f] border border-[#ffccc7]"
                : status === "failed"
                ? "bg-[#fff2f0] text-[#ff4d4f] border border-[#ffccc7]"
                : "bg-[#fafafa] text-[#888] border border-[#ddd]"
            }`}
          >
            Status: {status.charAt(0).toUpperCase() + status.slice(1)}
          </div>
        </div>
      </div>

      <div
        className="flex-1 overflow-y-auto p-3 text-xs leading-normal whitespace-pre-wrap break-words bg-white text-[#333]"
        ref={logContainerRef}
      >
        {logs.length > 0 ? (
          logs.map((log, index) => formatLog(log, index))
        ) : (
          <div className="text-[#999] italic py-5 text-center">
            Waiting for logs...
          </div>
        )}

        {error && (
          <div className="mt-2 p-2 rounded bg-[#fff2f0] text-[#ff4d4f] border border-[#ffccc7]">
            <strong>Error:</strong> {error}
          </div>
        )}
      </div>

      {/* Close button at the bottom */}
      <div className="p-2.5 flex justify-center border-t border-[#ddd] bg-[#f0f2f5]">
        <button
          className="py-1.5 px-4 bg-[#f5f5f5] border border-[#ddd] rounded text-sm font-medium cursor-pointer text-[#333] transition-all hover:bg-[#e6e6e6] hover:border-[#ccc]"
          onClick={onClose}
          title="Close log viewer"
        >
          Close
        </button>
      </div>
    </div>
  );
};

export default LogViewer;
