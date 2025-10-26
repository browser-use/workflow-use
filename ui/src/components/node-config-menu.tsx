import React, { useState, useEffect } from "react";
import { StepData, NodeConfigMenuProps } from "../types/node-config-menu.types";
import { fetchClient } from "../lib/api";

const toTitleCase = (str: string): string => {
  return str
    .split("_")
    .map((word) => {
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");
};

export const NodeConfigMenu: React.FC<NodeConfigMenuProps> = ({
  node,
  onClose,
  workflowFilename,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedStepData, setEditedStepData] = useState<StepData | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [localStepData, setLocalStepData] = useState<StepData | null>(null);
  const [cssSelectors, setCssSelectors] = useState<string[]>([]);
  const [newSelector, setNewSelector] = useState("");

  useEffect(() => {
    if (node && node.data && node.data.stepData) {
      setLocalStepData(node.data.stepData);
      setIsEditing(false);
      setEditedStepData(null);
      setError(null);
      setSuccess(false);
    }
  }, [node]);

  useEffect(() => {
    const handleEscKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscKey);

    return () => {
      document.removeEventListener("keydown", handleEscKey);
    };
  }, [onClose]);

  useEffect(() => {
    if (isEditing && editedStepData?.cssSelector && cssSelectors.length === 0) {
      setCssSelectors(editedStepData.cssSelector.split(" "));
    }
  }, [isEditing, editedStepData?.cssSelector, cssSelectors.length]);

  useEffect(() => {
    if (isEditing && !editedStepData && localStepData) {
      setEditedStepData({ ...localStepData });
    } else if (isEditing && !editedStepData && node?.data?.stepData) {
      setEditedStepData({ ...node.data.stepData });
    }
  }, [isEditing, editedStepData, localStepData, node]);

  if (!node || !node.data || !node.data.stepData) return null;

  const stepData: StepData = localStepData || node.data.stepData;

  const handleInputChange = (field: keyof StepData, value: string) => {
    if (editedStepData) {
      setEditedStepData({
        ...editedStepData,
        [field]: value,
      });
    }
  };

  const handleAddSelector = () => {
    if (newSelector.trim() !== "") {
      const updatedSelectors = [...cssSelectors, newSelector.trim()];
      setCssSelectors(updatedSelectors);
      setNewSelector("");

      // Update the editedStepData
      if (editedStepData) {
        setEditedStepData({
          ...editedStepData,
          cssSelector: updatedSelectors.join(" "),
        });
      }
    }
  };

  const handleRemoveSelector = (index: number) => {
    const updatedSelectors = cssSelectors.filter((_, i) => i !== index);
    setCssSelectors(updatedSelectors);

    if (editedStepData) {
      setEditedStepData({
        ...editedStepData,
        cssSelector: updatedSelectors.join(" "),
      });
    }
  };

  const handleSubmit = async () => {
    if (!editedStepData) return;

    if (cssSelectors.length > 0) {
      editedStepData.cssSelector = cssSelectors.join(" ");
    }

    setIsSubmitting(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await fetchClient.POST("/api/workflows/update", {
        body: {
          filename: workflowFilename ?? "",
          nodeId: parseInt(node.id),
          stepData: editedStepData as unknown as Record<string, never>,
        },
      });

      const result = response.data;

      if (result?.success) {
        setSuccess(true);
        setIsEditing(false);
        setLocalStepData(editedStepData);
        if (node && node.data) {
          node.data.stepData = editedStepData;
        }
      } else {
        setError(result?.error || "Failed to update workflow");
      }
    } catch (err) {
      setError(
        "Network error: " + (err instanceof Error ? err.message : String(err))
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditedStepData(null);
    setError(null);
    setCssSelectors([]);
    setNewSelector("");
  };

  return (
    <div className="fixed top-5 right-5 z-[1000] w-[450px] max-w-[90vw] max-h-[85vh] overflow-y-auto rounded-lg bg-[#2a2a2a] text-white shadow-2xl">
      {/* header */}
      <div className="flex items-center justify-between border-b border-gray-700 p-4">
        <div>{stepData.description}</div>
        <button
          onClick={onClose}
          className="text-2xl text-gray-400 hover:text-white"
        >
          ×
        </button>
      </div>

      <div className="p-4">
        {/* step type */}
        <div className="mb-3 break-words">
          <strong>Step Type:</strong>{" "}
          {isEditing ? (
            <select
              value={editedStepData?.type || "navigation"}
              onChange={(e) => handleInputChange("type", e.target.value)}
              className="ml-1 rounded border border-gray-600 bg-[#333] px-2 py-1 text-sm"
            >
              <option value="navigation">Navigation</option>
              <option value="click">Click</option>
              <option value="select_change">Select Change</option>
              <option value="input">Input</option>
            </select>
          ) : (
            toTitleCase(stepData.type)
          )}
        </div>

        {/* tab id */}
        {stepData.tabId !== null && !isEditing && (
          <div className="mb-3">
            <strong>Tab ID:</strong> {stepData.tabId}
          </div>
        )}

        {/* URL (only for first node) */}
        {(stepData.url || isEditing) && node.id === "0" && (
          <div className="mb-3">
            <strong>URL:</strong>
            {isEditing ? (
              <input
                type="text"
                value={editedStepData?.url || ""}
                onChange={(e) => handleInputChange("url", e.target.value)}
                className="mt-1 w-full rounded border border-gray-600 bg-[#333] px-2 py-1 text-sm"
              />
            ) : (
              <a
                href={stepData.url || ""}
                target="_blank"
                rel="noopener noreferrer"
                title={stepData.url || ""}
                className="ml-1 break-all text-blue-400 hover:underline"
              >
                {stepData.url && stepData.url.length > 40
                  ? `${stepData.url.slice(0, 37)}...`
                  : stepData.url}
              </a>
            )}
          </div>
        )}

        {/* CSS selectors */}
        {(stepData.cssSelector || isEditing) && (
          <div className="mb-3">
            <strong>CSS Selectors:</strong>
            {isEditing ? (
              <div className="mt-2">
                {/* chips */}
                <div className="flex flex-wrap gap-2">
                  {cssSelectors.map((sel, idx) => (
                    <div
                      key={idx}
                      className="flex items-center rounded bg-gray-700 pl-2"
                    >
                      <span
                        title={sel.length > 65 ? sel : undefined}
                        className="mr-1 whitespace-nowrap text-xs"
                      >
                        {sel.length > 65 ? `${sel.slice(0, 62)}...` : sel}
                      </span>
                      <button
                        onClick={() => handleRemoveSelector(idx)}
                        className="px-1 text-lg text-gray-400 hover:text-red-400"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>

                {/* add new */}
                <div className="mt-2 flex gap-2">
                  <input
                    type="text"
                    value={newSelector}
                    onChange={(e) => setNewSelector(e.target.value)}
                    className="flex-1 rounded border border-gray-600 bg-[#333] px-2 py-1 text-sm"
                    placeholder="Add selector..."
                  />
                  <button
                    onClick={handleAddSelector}
                    className="rounded bg-blue-400 px-2 text-lg leading-none hover:bg-blue-500"
                  >
                    +
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-1 flex flex-wrap gap-2">
                {stepData.cssSelector?.split(" ").map((sel, idx) => (
                  <span
                    key={idx}
                    title={sel.length > 65 ? sel : undefined}
                    className="rounded bg-gray-700 px-2 py-0.5 text-xs"
                  >
                    {sel.length > 65 ? `${sel.slice(0, 62)}...` : sel}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* XPath */}
        {(stepData.xpath || isEditing) && (
          <div className="mb-3 break-all">
            <strong>XPath:</strong>
            {isEditing ? (
              <input
                type="text"
                value={editedStepData?.xpath || ""}
                onChange={(e) => handleInputChange("xpath", e.target.value)}
                className="mt-1 w-full rounded border border-gray-600 bg-[#333] px-2 py-1 text-sm"
              />
            ) : (
              <span className="ml-1">
                {stepData.xpath && stepData.xpath.length > 40
                  ? `${stepData.xpath.slice(0, 37)}...`
                  : stepData.xpath}
              </span>
            )}
          </div>
        )}

        {/* Element tag */}
        {(stepData.elementTag || isEditing) && (
          <div className="mb-3">
            <strong>Element Tag:</strong>{" "}
            {isEditing ? (
              <input
                type="text"
                value={editedStepData?.elementTag || ""}
                onChange={(e) =>
                  handleInputChange("elementTag", e.target.value)
                }
                className="mt-1 rounded border border-gray-600 bg-[#333] px-2 py-1 text-sm"
              />
            ) : (
              <span className="ml-1">{`<${stepData.elementTag}>`}</span>
            )}
          </div>
        )}

        {/* Element text */}
        {(stepData.elementText || isEditing) && (
          <div className="mb-3 break-words">
            <strong>Element Text:</strong>
            {isEditing ? (
              <input
                type="text"
                value={editedStepData?.elementText || ""}
                onChange={(e) =>
                  handleInputChange("elementText", e.target.value)
                }
                className="mt-1 w-full rounded border border-gray-600 bg-[#333] px-2 py-1 text-sm"
              />
            ) : (
              <div className="mt-1">{stepData.elementText}</div>
            )}
          </div>
        )}

        {/* Selected text */}
        {(stepData.selectedText || isEditing) && (
          <div className="mb-3 break-words">
            <strong>Selected Text:</strong>
            {isEditing ? (
              <input
                type="text"
                value={editedStepData?.selectedText || ""}
                onChange={(e) =>
                  handleInputChange("selectedText", e.target.value)
                }
                className="mt-1 w-full rounded border border-gray-600 bg-[#333] px-2 py-1 text-sm"
              />
            ) : (
              <div className="mt-1">{stepData.selectedText}</div>
            )}
          </div>
        )}

        {/* Value */}
        {(stepData.value || isEditing) && (
          <div className="mb-3 break-words">
            <strong>Value:</strong>
            {isEditing ? (
              <input
                type="text"
                value={editedStepData?.value || ""}
                onChange={(e) => handleInputChange("value", e.target.value)}
                className="mt-1 w-full rounded border border-gray-600 bg-[#333] px-2 py-1 text-sm"
              />
            ) : (
              <div className="mt-1">{stepData.value}</div>
            )}
          </div>
        )}

        {/* output */}
        {stepData.output && (
          <div className="mt-4">
            <strong>Output:</strong>
            <pre className="mt-1 max-h-[300px] overflow-auto rounded bg-[#333] p-3 text-xs">
              {JSON.stringify(stepData.output, null, 2)}
            </pre>
          </div>
        )}

        {/* action buttons */}
        <div className="mt-4 flex justify-end gap-2">
          {isEditing ? (
            <>
              <button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="rounded bg-blue-400 px-3 py-1 text-sm hover:bg-blue-500 disabled:opacity-60"
              >
                {isSubmitting ? "Saving…" : "Save"}
              </button>
              <button
                onClick={handleCancel}
                className="rounded bg-gray-600 px-3 py-1 text-sm hover:bg-gray-500"
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              onClick={() => setIsEditing(true)}
              className="rounded bg-gray-700 px-3 py-1 text-sm hover:bg-gray-600"
            >
              Edit
            </button>
          )}
        </div>

        {/* messages */}
        {success && (
          <div className="mt-3 rounded bg-green-800/20 p-2 text-green-400">
            Changes saved successfully!
          </div>
        )}
        {error && (
          <div className="mt-3 rounded bg-red-800/20 p-2 text-red-300">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};
