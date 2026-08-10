import React, { useCallback, useEffect, useRef, useState } from "react";

const API_BASE = "http://localhost:8000";

type RecordingStatus = {
  status: "idle" | "recording" | "saving" | "done" | "error" | "no_data";
  message?: string | null;
  workflow_file?: string | null;
};

interface RecordButtonProps {
  onRecordingSaved: (workflowFile: string) => void;
}

const RecordButton: React.FC<RecordButtonProps> = ({ onRecordingSaved }) => {
  const [status, setStatus] = useState<RecordingStatus>({ status: "idle" });
  const [busy, setBusy] = useState(false);
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const applyStatus = useCallback(
    (next: RecordingStatus) => {
      setStatus(next);
      if (next.status !== "recording" && next.status !== "saving") {
        stopPolling();
        if (next.status === "done" && next.workflow_file) {
          onRecordingSaved(next.workflow_file);
        }
      }
    },
    [onRecordingSaved, stopPolling]
  );

  const poll = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/workflows/recordings/status`);
      applyStatus((await res.json()) as RecordingStatus);
    } catch {
      /* backend briefly unreachable — keep polling */
    }
  }, [applyStatus]);

  const startPolling = useCallback(() => {
    stopPolling();
    pollRef.current = window.setInterval(poll, 2000);
  }, [poll, stopPolling]);

  useEffect(() => stopPolling, [stopPolling]);

  const start = async () => {
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/workflows/recordings/start`, {
        method: "POST",
      });
      applyStatus((await res.json()) as RecordingStatus);
      startPolling();
    } catch (e) {
      setStatus({ status: "error", message: String(e) });
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/workflows/recordings/stop`, {
        method: "POST",
      });
      applyStatus((await res.json()) as RecordingStatus);
      if ((status.status as string) === "saving") startPolling();
    } catch (e) {
      setStatus({ status: "error", message: String(e) });
    } finally {
      setBusy(false);
    }
  };

  const isRecording = status.status === "recording" || status.status === "saving";

  return (
    <div className="mb-3">
      <button
        onClick={isRecording ? stop : start}
        disabled={busy}
        className={`w-full rounded py-2 text-sm font-semibold text-white transition-colors ${
          isRecording
            ? "bg-red-600 hover:bg-red-700"
            : "bg-blue-500 hover:bg-blue-600"
        } ${busy ? "opacity-60" : ""}`}
      >
        {isRecording ? "■ Stop Recording" : "● Record New Workflow"}
      </button>

      {status.status === "recording" && (
        <p className="mt-2 text-xs text-[#aaa]">
          Recording… interact in the opened browser window, then click Stop (or
          close the browser).
        </p>
      )}
      {status.status === "saving" && (
        <p className="mt-2 text-xs text-[#aaa]">Saving recording…</p>
      )}
      {status.status === "done" && status.workflow_file && (
        <p className="mt-2 text-xs text-green-400">
          Saved: {status.workflow_file}
        </p>
      )}
      {(status.status === "error" || status.status === "no_data") && (
        <p className="mt-2 text-xs text-red-400">
          {status.message ?? "Recording failed"}
        </p>
      )}
    </div>
  );
};

export default RecordButton;
