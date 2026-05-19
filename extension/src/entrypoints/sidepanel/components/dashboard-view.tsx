import React, { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";

interface WorkflowItem {
  name: string;
  executing?: boolean;
  taskId?: string;
}

export const DashboardView: React.FC = () => {
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [executingWorkflows, setExecutingWorkflows] = useState<Set<string>>(new Set());
  const [browserExecution, setBrowserExecution] = useState<{
    state: string;
    currentStepIndex: number;
    totalSteps: number;
    workflowName: string;
  } | null>(null);

  const fetchWorkflows = useCallback(async () => {
    try {
      const response = await chrome.runtime.sendMessage({
        type: "API_REQUEST",
        payload: { endpoint: "/api/workflows", method: "GET" },
      });

      if (response?.success && response.data?.workflows) {
        setWorkflows(
          response.data.workflows.map((name: string) => ({ name }))
        );
        setError(null);
      } else {
        setError("Failed to load workflows");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWorkflows();

    // Listen for execution status updates
    const listener = (message: { type: string; payload: typeof browserExecution }) => {
      if (message.type === "execution_status_updated") {
        setBrowserExecution(message.payload);
      }
    };
    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, [fetchWorkflows]);

  const executeInBrowser = async (workflowName: string) => {
    try {
      const response = await chrome.runtime.sendMessage({
        type: "EXECUTE_IN_BROWSER",
        payload: { workflowName },
      });
      if (!response?.success) {
        setError(`Failed: ${response?.error || "Unknown error"}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Execution failed");
    }
  };

  const stopExecution = () => {
    chrome.runtime.sendMessage({ type: "STOP_EXECUTION" });
  };

  const executeWorkflow = async (workflowName: string) => {
    setExecutingWorkflows((prev) => new Set(prev).add(workflowName));
    try {
      const response = await chrome.runtime.sendMessage({
        type: "API_REQUEST",
        payload: {
          endpoint: "/api/workflows/execute",
          method: "POST",
          body: { name: workflowName, inputs: {} },
        },
      });

      if (response?.success && response.data?.success) {
        // Poll for status
        const taskId = response.data.task_id;
        pollTaskStatus(taskId, workflowName);
      } else {
        setExecutingWorkflows((prev) => {
          const next = new Set(prev);
          next.delete(workflowName);
          return next;
        });
        setError(`Failed to execute: ${response?.data?.detail || "Unknown error"}`);
      }
    } catch (err) {
      setExecutingWorkflows((prev) => {
        const next = new Set(prev);
        next.delete(workflowName);
        return next;
      });
      setError(err instanceof Error ? err.message : "Execution failed");
    }
  };

  const pollTaskStatus = async (taskId: string, workflowName: string) => {
    const poll = async () => {
      try {
        const response = await chrome.runtime.sendMessage({
          type: "API_REQUEST",
          payload: {
            endpoint: `/api/workflows/tasks/${taskId}/status`,
            method: "GET",
          },
        });

        if (response?.success) {
          const status = response.data?.status;
          if (status === "completed" || status === "failed" || status === "cancelled") {
            setExecutingWorkflows((prev) => {
              const next = new Set(prev);
              next.delete(workflowName);
              return next;
            });
            if (status === "failed") {
              setError(`Workflow failed: ${response.data?.error || "Unknown error"}`);
            }
            return; // Stop polling
          }
        }
        // Continue polling
        setTimeout(poll, 2000);
      } catch {
        setExecutingWorkflows((prev) => {
          const next = new Set(prev);
          next.delete(workflowName);
          return next;
        });
      }
    };
    setTimeout(poll, 2000);
  };

  const deleteWorkflow = async (workflowName: string) => {
    if (!confirm(`Delete workflow "${workflowName}"?`)) return;
    // Note: The backend doesn't have a delete endpoint yet.
    // For now, we show the user a note about this.
    setError("Delete is not yet supported from the extension. Remove the file from the tmp/ folder.");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-sm text-gray-500">Loading workflows...</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Workflows</h2>
          <p className="text-xs text-gray-500">
            {workflows.length} workflow{workflows.length !== 1 ? "s" : ""} saved
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchWorkflows}
          className="text-xs px-3 py-1"
        >
          Refresh
        </Button>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mx-3 mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 text-red-500 hover:text-red-700 font-medium"
          >
            ×
          </button>
        </div>
      )}

      {/* Workflow List */}
      <div className="flex-grow overflow-y-auto p-3 space-y-2">
        {workflows.length === 0 ? (
          <div className="text-center py-12 space-y-3">
            <div className="text-4xl">📭</div>
            <p className="text-sm text-gray-600">No workflows yet</p>
            <p className="text-xs text-gray-400">
              Record a workflow using the Record tab, or place .workflow.yaml files in the tmp/ folder
            </p>
          </div>
        ) : (
          workflows.map((wf) => {
            const isExecuting = executingWorkflows.has(wf.name);
            // Extract display name from filename
            const displayName = wf.name
              .replace(/\.workflow\.(json|yaml|yml)$/, "")
              .replace(/_/g, " ");

            return (
              <div
                key={wf.name}
                className="border border-gray-200 rounded-lg p-3 hover:border-gray-300 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0 mr-3">
                    <h3 className="text-sm font-medium text-gray-900 truncate capitalize">
                      {displayName}
                    </h3>
                    <p className="text-[10px] text-gray-400 truncate font-mono">
                      {wf.name}
                    </p>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    {browserExecution?.state === "running" && browserExecution.workflowName === wf.name ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={stopExecution}
                        className="text-xs px-2.5 py-1 h-7 text-red-600 border-red-300"
                      >
                        ⏹ Stop
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => executeInBrowser(wf.name)}
                        disabled={isExecuting || browserExecution?.state === "running"}
                        className="text-xs px-2.5 py-1 h-7"
                        title="Replay in THIS browser (keeps your login sessions)"
                      >
                        ▶ Run
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => deleteWorkflow(wf.name)}
                      className="text-xs px-2 py-1 h-7 text-red-500 hover:text-red-700"
                    >
                      🗑
                    </Button>
                  </div>
                </div>
                {/* Execution progress bar */}
                {browserExecution && browserExecution.workflowName === wf.name && browserExecution.state !== "idle" && (
                  <div className="mt-2 pt-2 border-t border-gray-100">
                    <div className="flex items-center justify-between text-[10px] text-gray-500 mb-1">
                      <span>
                        {browserExecution.state === "running" && "Executing..."}
                        {browserExecution.state === "waiting_nav" && "Waiting for page load..."}
                        {browserExecution.state === "healing" && "Self-healing..."}
                        {browserExecution.state === "completed" && "Completed!"}
                        {browserExecution.state === "failed" && "Failed"}
                        {browserExecution.state === "stopped" && "Stopped"}
                      </span>
                      <span>
                        Step {browserExecution.currentStepIndex + 1} / {browserExecution.totalSteps}
                      </span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-1.5">
                      <div
                        className={`h-1.5 rounded-full transition-all duration-300 ${
                          browserExecution.state === "completed" ? "bg-green-500" :
                          browserExecution.state === "failed" ? "bg-red-500" :
                          browserExecution.state === "healing" ? "bg-yellow-500" :
                          "bg-blue-500"
                        }`}
                        style={{
                          width: `${Math.max(5, ((browserExecution.currentStepIndex) / browserExecution.totalSteps) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
