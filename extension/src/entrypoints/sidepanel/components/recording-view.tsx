import React, { useState } from "react";
import { useWorkflow } from "../context/workflow-provider";
import { Button } from "@/components/ui/button";
import { ToggleButton } from "@/components/ui/button";
import { EventViewer } from "./event-viewer"; // Import EventViewer

export const RecordingView: React.FC = () => {
  const {
    stopRecording,
    workflow,
    stopHighlighting,
    startHighlighting,
    highlightingStatus,
  } = useWorkflow();
  const stepCount = workflow?.steps?.length || 0;

  const toggleHighlighting = () => {
    if (highlightingStatus === "highlighting_enabled") {
      stopHighlighting();
    } else {
      startHighlighting();
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center space-x-2">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
          </span>
          <span className="text-sm font-medium">
            Recording ({stepCount} steps)
          </span>
        </div>
        <ToggleButton
          checked={highlightingStatus === "highlighting_enabled"}
          onCheckedChange={toggleHighlighting}
          onLabel="Highlight On"
          offLabel="Highlight Off"
          aria-label="Toggle highlighting"
        />
        <Button variant="destructive" size="sm" onClick={stopRecording}>
          Stop Recording
        </Button>
      </div>
      <div className="flex-grow overflow-hidden p-4">
        {/* EventViewer will now take full available space within this div */}
        <EventViewer />
      </div>
    </div>
  );
};
