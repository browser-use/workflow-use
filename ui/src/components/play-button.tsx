import React, { useState } from "react";
import LogViewer from "./log-viewer";
import { PlayButtonProps, InputField } from "../types/play-button.types";

export const PlayButton: React.FC<PlayButtonProps> = ({
  workflowName,
  workflowMetadata,
}) => {
  const [showModal, setShowModal] = useState<boolean>(false);
  const [showLogViewer, setShowLogViewer] = useState<boolean>(false);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [inputFields, setInputFields] = useState<InputField[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [logPosition, setLogPosition] = useState<number>(0);
  const [workflowStatus, setWorkflowStatus] = useState<string>("idle");

  const openModal = () => {
    if (!workflowName) return;

    setShowModal(true);
    setError(null);

    if (workflowMetadata && workflowMetadata.input_schema) {
      const fields = workflowMetadata.input_schema.map((input: { name: string; type: string; required: boolean }) => ({
        name: input.name,
        type: input.type,
        required: input.required,
        value: input.type === "boolean" ? false : "",
      }));
      setInputFields(fields);
    } else {
      setInputFields([]);
    }
  };

  const closeModal = () => {
    setShowModal(false);

    if (!isRunning) {
      resetState();
    }
  };

  const closeLogViewer = () => {
    setShowLogViewer(false);
    resetState();
  };

  const resetState = () => {
    setIsRunning(false);
    setError(null);
    setInputFields([]);
    setTaskId(null);
    setLogPosition(0);
    setWorkflowStatus("idle");
  };

  const handleInputChange = (index: number, value: string | number | boolean) => {
    const updatedFields = [...inputFields];
    if (updatedFields[index]) {
      updatedFields[index].value = value;
      setInputFields(updatedFields);
    }
  };

  const executeWorkflow = async () => {
    if (!workflowName) return;

    const missingInputs = inputFields.filter(
      (field) => field.required && !field.value
    );
    if (missingInputs.length > 0) {
      setError(
        `Missing required inputs: ${missingInputs
          .map((f) => f.name)
          .join(", ")}`
      );
      return;
    }

    setIsRunning(true);
    setError(null);
    setTaskId(null);
    setLogPosition(0);
    setWorkflowStatus("idle");

    try {
      const inputs: Record<string, string | number | boolean> = {};
      inputFields.forEach((field) => {
        inputs[field.name] = field.value;
      });

      const response = await fetch(
        "http://127.0.0.1:8000/api/workflows/execute",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: workflowName,
            inputs,
          }),
        }
      );

      const data = await response.json();
      setTaskId(data.task_id);
      setLogPosition(data.log_position);
      setIsRunning(true);
      setShowLogViewer(true);
      setShowModal(false);
    } catch (err) {
      console.error("Failed to execute workflow:", err);
      setError("An error occurred while executing the workflow");
    }
  };

  const handleStatusChange = (status: string) => {
    setWorkflowStatus(status);

    if (
      status === "completed" ||
      status === "failed" ||
      status === "cancelled"
    ) {
      setIsRunning(false);
    }
  };

  const handleCancelWorkflow = () => {
    setWorkflowStatus("cancelling");
  };

  const handleWorkflowError = (errorMessage: string) => {
    setError(errorMessage);
  };

  if (!workflowName) return null;

  return (
    <div>
      {/* play button */}
      <button
        title="Execute workflow"
        onClick={openModal}
        className="z-10 flex h-9 w-9 items-center justify-center rounded-full bg-[#2a2a2a] text-white shadow transition-transform duration-200 ease-in-out hover:scale-105 hover:bg-blue-500"
      >
        ▶
      </button>

      {/* parameter‑input modal */}
      {showModal && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50">
          <div className="flex max-h-[80vh] w-[600px] max-w-[80vw] flex-col overflow-hidden rounded-lg bg-[#2a2a2a] text-white shadow-2xl">
            {/* header */}
            <div className="flex items-center justify-between border-b border-gray-700 p-4">
              <h3 className="m-0 text-lg">
                Execute Workflow: {workflowMetadata?.name || workflowName}
              </h3>
              <button
                onClick={closeModal}
                className="text-2xl text-gray-400 hover:text-white"
              >
                ×
              </button>
            </div>

            {/* content */}
            <div className="flex-1 overflow-y-auto p-4">
              {error && (
                <div className="mb-4 rounded bg-red-800/20 p-2 text-red-300">
                  {error}
                </div>
              )}

              {inputFields.length ? (
                <div className="mb-5">
                  <h4 className="mb-3 mt-0 text-base text-gray-300">
                    Input Parameters
                  </h4>

                  {inputFields.map((f, i) => (
                    <div key={f.name} className="mb-3">
                      <label className="mb-1 block text-sm text-gray-300">
                        {f.name}
                        {f.required && (
                          <span className="ml-1 text-red-400">*</span>
                        )}
                        <span className="ml-1 text-xs text-gray-500">
                          ({f.type})
                        </span>
                      </label>

                      {f.type === "boolean" ? (
                        <input
                          type="checkbox"
                          checked={f.value as boolean}
                          onChange={(e) =>
                            handleInputChange(i, e.target.checked)
                          }
                        />
                      ) : (
                        <input
                          type={f.type === "number" ? "number" : "text"}
                          value={f.value as string | number}
                          onChange={(e) => handleInputChange(i, e.target.value)}
                          className="w-full rounded border border-gray-600 bg-[#333] px-3 py-2 text-sm text-white"
                        />
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p>No input parameters required for this workflow.</p>
              )}

              <div className="mt-5 flex justify-end gap-3">
                <button
                  onClick={closeModal}
                  className="rounded bg-gray-600 px-4 py-2 text-sm text-white hover:bg-gray-500"
                >
                  Cancel
                </button>
                <button
                  onClick={executeWorkflow}
                  disabled={isRunning}
                  className="rounded bg-blue-400 px-4 py-2 text-sm text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-gray-600 disabled:opacity-70"
                >
                  Execute Workflow
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* log viewer */}
      {showLogViewer && taskId && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50">
          <div className="flex max-h-[80vh] w-[650px] max-w-[80vw] flex-col overflow-hidden rounded-lg bg-[#2a2a2a] text-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-700 p-4">
              <div>
                Workflow Execution
                {workflowStatus !== "running" &&
                  ` (${workflowStatus
                    .charAt(0)
                    .toUpperCase()}${workflowStatus.slice(1)})`}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              <LogViewer
                taskId={taskId}
                initialPosition={logPosition}
                onStatusChange={handleStatusChange}
                onError={handleWorkflowError}
                onCancel={handleCancelWorkflow}
                onClose={closeLogViewer}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
