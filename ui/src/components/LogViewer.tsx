import React, { useEffect, useRef, useState } from 'react';
import { useAppContext } from '@/contexts/AppContext';

interface LogViewerProps {
  taskId: string;
  onClose: () => void;
}

export const LogViewer: React.FC<LogViewerProps> = ({ taskId, onClose }) => {
  const {
    logData,
    workflowStatus,
    workflowError,
    startPollingLogs,
    stopPollingLogs,
    cancelWorkflowExecution,
  } = useAppContext();

  const [isCancelling, setIsCancelling] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    startPollingLogs(taskId);
    return () => {
      stopPollingLogs();
    };
  }, [taskId]);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logData]);

  const handleCancel = async () => {
    if (workflowStatus !== 'running') return;
    setIsCancelling(true);
    try {
      await cancelWorkflowExecution(taskId);
    } finally {
      setIsCancelling(false);
    }
  };

  const downloadLogs = () => {
    if (logData.length === 0) return;
    const blob = new Blob([logData.join('')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `workflow-logs-${taskId}.txt`;
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
            {workflowStatus === 'running' && (
              <button
                className={`flex items-center gap-1 py-1 px-2 bg-[#fff2f0] border border-[#ffccc7] rounded text-xs text-[#ff4d4f] transition hover:bg-[#fff1f0] hover:border-[#ffa39e] ${
                  isCancelling ? 'opacity-60 cursor-not-allowed' : ''
                }`}
                onClick={handleCancel}
                disabled={isCancelling}
              >
                Cancel
              </button>
            )}
            {logData.length > 0 && (
              <button
                className="flex items-center gap-1 py-1 px-2 bg-[#f5f5f5] border border-[#ddd] rounded text-xs text-[#333] hover:bg-[#e6e6e6] hover:border-[#ccc]"
                onClick={downloadLogs}
              >
                Download
              </button>
            )}
          </div>
          <div
            className={`py-0.5 px-2 rounded text-xs font-medium ${
              workflowStatus === 'running'
                ? 'bg-[#e6f7ff] text-[#1890ff] border border-[#91d5ff]'
                : workflowStatus === 'completed'
                ? 'bg-[#f6ffed] text-[#52c41a] border border-[#b7eb8f]'
                : workflowStatus === 'cancelling'
                ? 'bg-[#fff2f0] text-orange border border-[#ffccc7]'
                : workflowStatus === 'cancelled'
                ? 'bg-[#fff2f0] text-[#ff4d4f] border border-[#ffccc7]'
                : workflowStatus === 'failed'
                ? 'bg-[#fff2f0] text-[#ff4d4f] border border-[#ffccc7]'
                : 'bg-[#fafafa] text-[#888] border border-[#ddd]'
            }`}
          >
            Status:{' '}
            {workflowStatus.charAt(0).toUpperCase() + workflowStatus.slice(1)}
          </div>
        </div>
      </div>

      <div
        className="flex-1 overflow-y-auto p-3 text-xs leading-normal whitespace-pre-wrap break-words bg-white text-[#333]"
        ref={logContainerRef}
      >
        {logData.length > 0 ? (
          logData.map((log, index) => formatLog(log, index))
        ) : (
          <div className="text-[#999] italic py-5 text-center">
            Waiting for logs...
          </div>
        )}

        {workflowError && (
          <div className="mt-2 p-2 rounded bg-[#fff2f0] text-[#ff4d4f] border border-[#ffccc7]">
            <strong>Error:</strong> {workflowError}
          </div>
        )}
      </div>

      <div className="p-2.5 flex justify-center border-t border-[#ddd] bg-[#f0f2f5]">
        <button
          className="py-1.5 px-4 bg-[#f5f5f5] border border-[#ddd] rounded text-sm font-medium text-[#333] hover:bg-[#e6e6e6] hover:border-[#ccc]"
          onClick={onClose}
        >
          Close
        </button>
      </div>
    </div>
  );
};
