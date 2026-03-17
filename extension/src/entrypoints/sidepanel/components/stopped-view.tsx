import React, { useState } from "react";
import { useWorkflow } from "../context/workflow-provider";
import { Button } from "@/components/ui/button";
import { EventViewer } from "./event-viewer";

export const StoppedView: React.FC = () => {
  const { discardAndStartNew, workflow } = useWorkflow();
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [workflowName, setWorkflowName] = useState("");
  const [workflowDescription, setWorkflowDescription] = useState("");
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);

  const downloadJson = (customName?: string, customDescription?: string) => {
    if (!workflow) return;

    // Create enhanced workflow with user inputs
    const enhancedWorkflow = {
      ...workflow,
      name: customName || workflow.name,
      description: customDescription || workflow.description,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      workflow_analysis: `Recorded workflow with ${workflow.steps?.length || 0} steps. ${workflow.steps?.some(s => (s as any).type === 'extract') ? 'Includes AI extraction steps for intelligent data gathering.' : ''}`
    };

    // Sanitize workflow name for filename
    const safeName = enhancedWorkflow.name
      ? enhancedWorkflow.name.replace(/[^a-z0-9._-]/gi, "_").toLowerCase()
      : "workflow";

    const blob = new Blob([JSON.stringify(enhancedWorkflow, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    // Generate filename e.g., my_workflow_name_2023-10-27_10-30-00.json
    const timestamp = new Date()
      .toISOString()
      .replace(/[:.]/g, "-")
      .slice(0, 19);
    // Use sanitized name instead of domain
    a.download = `${safeName}_${timestamp}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleQuickDownload = () => {
    downloadJson();
  };

  const saveToBackend = async (customName: string, customDescription?: string) => {
    if (!workflow) return;

    setSaveStatus("saving");
    setSaveError(null);

    const enhancedWorkflow = {
      ...workflow,
      name: customName,
      description: customDescription || workflow.description,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      workflow_analysis: `Recorded workflow with ${workflow.steps?.length || 0} steps. ${workflow.steps?.some(s => (s as any).type === 'extract') ? 'Includes AI extraction steps for intelligent data gathering.' : ''}`
    };

    // Remove internal fields from steps before saving
    const cleanedWorkflow = {
      ...enhancedWorkflow,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      steps: enhancedWorkflow.steps?.map((step: any) => {
        const cleaned = { ...step };
        delete cleaned.timestamp;
        delete cleaned.tabId;
        delete cleaned.frameUrl;
        delete cleaned.xpath;
        delete cleaned.elementTag;
        delete cleaned.elementText;
        delete cleaned.screenshot;
        // Convert targetText to target_text
        if (cleaned.targetText) {
          cleaned.target_text = cleaned.targetText;
          delete cleaned.targetText;
        }
        return cleaned;
      }),
    };

    try {
      const response = await chrome.runtime.sendMessage({
        type: "SAVE_WORKFLOW_TO_BACKEND",
        payload: { workflow: cleanedWorkflow, name: customName },
      });

      if (response?.success) {
        setSaveStatus("saved");
        setTimeout(() => setSaveStatus("idle"), 3000);
      } else {
        setSaveStatus("error");
        setSaveError(response?.data?.error || response?.error || "Failed to save");
      }
    } catch (error) {
      setSaveStatus("error");
      setSaveError(error instanceof Error ? error.message : "Connection failed");
    }
  };

  const handleSaveWithDetails = () => {
    if (workflowName.trim()) {
      // Save to backend AND download locally
      saveToBackend(workflowName.trim(), workflowDescription.trim());
      downloadJson(workflowName.trim(), workflowDescription.trim());
      setShowSaveDialog(false);
      setWorkflowName("");
      setWorkflowDescription("");
    }
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hasExtractionSteps = workflow?.steps?.some(step => (step as any).type === 'extract');
  const stepCount = workflow?.steps?.length || 0;

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Recording Finished</h2>
          <p className="text-sm text-gray-500">
            {stepCount} steps recorded{hasExtractionSteps && " • Includes AI extraction"}
          </p>
        </div>
        <div className="flex space-x-2">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={discardAndStartNew}
            className="text-xs px-3 py-1"
          >
            Discard & Start New
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setShowSaveDialog(true)}
            disabled={!workflow || !workflow.steps || workflow.steps.length === 0}
            className="text-xs px-3 py-1"
          >
            Save As...
          </Button>
          <Button
            size="sm"
            onClick={handleQuickDownload}
            disabled={!workflow || !workflow.steps || workflow.steps.length === 0}
            className="text-xs px-3 py-1"
          >
            Quick Download
          </Button>
        </div>
      </div>

      {/* Save Status Banner */}
      {saveStatus === "saved" && (
        <div className="mx-3 mt-2 p-2 bg-green-50 border border-green-200 rounded text-xs text-green-700">
          Workflow saved to backend! View it in the Workflows tab.
        </div>
      )}
      {saveStatus === "error" && (
        <div className="mx-3 mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
          Save failed: {saveError}
          <button onClick={() => setSaveStatus("idle")} className="ml-2 font-medium">x</button>
        </div>
      )}
      
      {/* Save Dialog */}
      {showSaveDialog && (
        <div className="p-4 bg-gray-50 border-b border-gray-200">
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-gray-900">Save Workflow</h3>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Workflow Name *
              </label>
              <input
                type="text"
                value={workflowName}
                onChange={(e) => setWorkflowName(e.target.value)}
                placeholder="e.g., Flight Search and Price Extraction"
                className="w-full p-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={workflowDescription}
                onChange={(e) => setWorkflowDescription(e.target.value)}
                placeholder="Describe what this workflow does and when to use it..."
                className="w-full p-2 text-sm border border-gray-300 rounded resize-none focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                rows={3}
              />
            </div>
            {hasExtractionSteps && (
              <div className="p-2 bg-blue-50 rounded text-xs text-blue-700">
                💡 This workflow includes AI extraction steps that will intelligently gather data from web pages.
              </div>
            )}
            <div className="flex space-x-2">
              <Button 
                size="sm" 
                onClick={handleSaveWithDetails}
                disabled={!workflowName.trim()}
                className="text-xs px-3 py-1"
              >
                Save Workflow
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => {
                  setShowSaveDialog(false);
                  setWorkflowName("");
                  setWorkflowDescription("");
                }}
                className="text-xs px-3 py-1"
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
      
      {/* Event Viewer */}
      <div className="flex-grow overflow-hidden p-4">
        <EventViewer />
      </div>
    </div>
  );
};
