import React, { useState } from "react";
import { useWorkflow } from "../context/workflow-provider";
import { Button } from "@/components/ui/button";
import { EventViewer } from "./event-viewer"; // Import EventViewer

export const RecordingView: React.FC = () => {
  const { stopRecording, workflow, recordingStatus } = useWorkflow();
  const stepCount = workflow?.steps?.length || 0;
  const [showExtractionDialog, setShowExtractionDialog] = useState(false);
  const [extractionGoal, setExtractionGoal] = useState("");

  const handleAddExtraction = () => {
    if (extractionGoal.trim()) {
      const payload = {
        extractionGoal: extractionGoal.trim(),
        timestamp: Date.now(),
      };
      
      console.log("🤖 Sending extraction step request:", payload);
      console.log("📊 Current workflow stats:", stats);
      console.log("📝 Current workflow:", workflow);
      console.log("🔴 Recording status:", recordingStatus);
      
      // Set up a timeout to handle potential message port issues
      let timeoutId: NodeJS.Timeout;
      let responseReceived = false;
      
      const timeoutPromise = new Promise((_, reject) => {
        timeoutId = setTimeout(() => {
          if (!responseReceived) {
            reject(new Error("Request timeout - no response received within 5 seconds"));
          }
        }, 5000);
      });
      
      // Send extraction step to background script
      chrome.runtime.sendMessage({
        type: "ADD_EXTRACTION_STEP",
        payload: payload
      }, (response) => {
        responseReceived = true;
        clearTimeout(timeoutId);
        
        console.log("📨 Extraction step response:", response);
        
        if (chrome.runtime.lastError) {
          console.error("❌ Chrome runtime error:", chrome.runtime.lastError);
          alert(`Chrome runtime error: ${chrome.runtime.lastError.message}\n\nTry reloading the extension and starting a new recording.`);
          return;
        }
        
        if (response?.status === "added") {
          console.log("✅ Extraction step added successfully");
          setExtractionGoal("");
          setShowExtractionDialog(false);
        } else {
          console.error("❌ Failed to add extraction step:", response);
          const errorMessage = response?.message || 'Unknown error';
          alert(`Failed to add extraction step: ${errorMessage}`);
        }
      });
      
      // Handle timeout case
      timeoutPromise.catch((error) => {
        if (!responseReceived) {
          console.error("❌ Request timeout:", error);
          alert("Request timed out. Please try again or reload the extension.");
        }
      });
      
    } else {
      console.warn("⚠️ Extraction goal is empty");
    }
  };

  // Get workflow stats
  const stats = React.useMemo(() => {
    if (!workflow?.steps) return { actions: 0, extractions: 0, navigations: 0 };

    const actions = workflow.steps.filter(s => ['click', 'input', 'key_press'].includes(s.type)).length;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const extractions = workflow.steps.filter(s => (s as any).type === 'extract').length;
    const navigations = workflow.steps.filter(s => s.type === 'navigation').length;

    return { actions, extractions, navigations };
  }, [workflow?.steps]);

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200 bg-white">
        <div className="flex items-center space-x-3">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
          </span>
          <div>
            <span className="text-sm font-medium text-gray-900">
              Recording ({stepCount} steps)
            </span>
            <div className="text-xs text-gray-500">
              {stats.actions} actions • {stats.navigations} nav • {stats.extractions} AI extractions
            </div>
            {/* Debug status */}
            <div className="text-xs text-blue-600 font-mono">
              Status: {recordingStatus}
            </div>
          </div>
        </div>
        <div className="flex space-x-2">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setShowExtractionDialog(true)}
            className="bg-blue-50 hover:bg-blue-100 text-blue-700 border-blue-200 text-xs px-3 py-1"
          >
            🤖 Extract with AI
          </Button>
          <Button 
            variant="destructive" 
            size="sm" 
            onClick={stopRecording}
            className="text-xs px-3 py-1"
          >
            Stop Recording
          </Button>
        </div>
      </div>
      
      {/* Extraction Dialog */}
      {showExtractionDialog && (
        <div className="p-4 bg-blue-50 border-b border-blue-200">
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-blue-900">Add AI Extraction Step</h3>
            <p className="text-xs text-blue-700">
              Describe what information you want to extract from the current page:
            </p>
            <textarea
              value={extractionGoal}
              onChange={(e) => setExtractionGoal(e.target.value)}
              placeholder="e.g., Extract flight prices, departure times, airlines, and booking links from the search results page"
              className="w-full p-2 text-sm border border-blue-200 rounded resize-none focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              rows={3}
            />
            <div className="flex space-x-2">
              <Button 
                size="sm" 
                onClick={handleAddExtraction}
                disabled={!extractionGoal.trim()}
                className="text-xs px-3 py-1"
              >
                Add Extraction
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => {
                  setShowExtractionDialog(false);
                  setExtractionGoal("");
                }}
                className="text-xs px-3 py-1"
              >
                Cancel
              </Button>
            </div>
            <div className="text-xs text-blue-600 bg-blue-100 p-2 rounded">
              💡 Tip: Be specific about what data you want (prices, dates, names, etc.) and the format you prefer
            </div>
          </div>
        </div>
      )}

      {/* Workflow preview/tips */}
      {stepCount > 0 && (
        <div className="px-4 py-2 bg-gray-50 border-b text-xs text-gray-600">
          <div className="flex items-center justify-between">
            <span className="flex items-center space-x-1">
              {stats.navigations > 0 && <span>🧭 Navigation</span>}
              {stats.actions > 0 && <span>→ 🖱️ {stats.actions} interactions</span>}
              {stats.extractions > 0 && <span>→ 🤖 {stats.extractions} AI extractions</span>}
            </span>
            {stepCount >= 3 && stats.extractions === 0 && (
              <span className="text-blue-600 font-medium">
                💡 Add AI extraction to capture data
              </span>
            )}
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
