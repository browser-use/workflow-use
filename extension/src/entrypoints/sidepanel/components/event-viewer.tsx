import React, { useEffect, useRef } from "react";
import {
  ClickStep,
  InputStep,
  KeyPressStep,
  NavigationStep,
  ScrollStep,
  Step,
} from "../../../lib/workflow-types"; // Adjust path as needed
import { useWorkflow } from "../context/workflow-provider";

// Helper to get the specific screenshot for a step
const getScreenshot = (step: Step): string | undefined => {
  if ("screenshot" in step) {
    return step.screenshot;
  }
  return undefined;
};

// Helper function to format step details based on type
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const formatStepDetails = (step: Step): string => {
  switch (step.type) {
    case "navigation":
      return (step as NavigationStep).url;
    case "click":
      return (step as ClickStep).targetText || (step as ClickStep).elementText || (step as ClickStep).cssSelector || "Click action";
    case "input": {
      const s = step as InputStep;
      const value = s.value || "";
      const target = s.targetText || s.cssSelector || "Input field";
      return `${target}: "${value}"`;
    }
    case "key_press":
      return `Key: ${(step as KeyPressStep).key}`;
    case "scroll":
      return `(${(step as ScrollStep).scrollX}, ${(step as ScrollStep).scrollY})`;
    case "extract":
      return "AI Extraction";
    default:
      return "Unknown action";
  }
};

// Helper function to get step icon based on type
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const getStepIcon = (step: Step): string => {
  switch (step.type) {
    case "navigation":
      return "🔗";
    case "click":
      return "👆";
    case "input":
      return "✏️";
    case "key_press":
      return "⌨️";
    case "scroll":
      return "📜";
    case "extract":
      return "🤖";
    default:
      return "❓";
  }
};

// Helper function to get background color based on step type
const getStepBgColor = (step: Step, isSelected: boolean): string => {
  if (isSelected) {
    switch (step.type) {
      case "extract":
        return "bg-blue-100 border-blue-300";
      default:
        return "bg-blue-50 border-blue-200";
    }
  } else {
    switch (step.type) {
      case "extract":
        return "bg-blue-25 border-blue-100 hover:bg-blue-50";
      default:
        return "bg-white border-gray-200 hover:bg-gray-50";
    }
  }
};

// Component to render a single step as a card
const StepCard: React.FC<{
  step: Step;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
}> = ({ step, index, isSelected, onSelect }) => {
  const screenshot = getScreenshot(step);
  const canShowScreenshot = ["click", "input", "key_press"].includes(step.type);

  // --- Step Summary Renderer (Top part of the card) ---
  const renderStepSummary = (step: Step) => {
    switch (step.type) {
      case "click": {
        const s = step as ClickStep;
        // Enhanced display for radio buttons
        if (s.radioButtonInfo && s.radioButtonInfo.fieldName && s.radioButtonInfo.optionValue) {
          return (
            <div className="flex items-center space-x-2">
              <span className="text-lg">📻</span>
              <span className="truncate">
                Select <strong>{s.radioButtonInfo.optionValue}</strong> for <strong>{s.radioButtonInfo.fieldName}</strong>
              </span>
            </div>
          );
        }
        // Standard click display
        const targetDescription = s.targetText || s.elementText || s.elementTag;
        return (
          <div className="flex items-center space-x-2">
            <span className="text-lg">🖱️</span>
            <span className="truncate">
              Click on <strong>{targetDescription}</strong>
            </span>
          </div>
        );
      }
      case "input": {
        const s = step as InputStep;
        const targetDescription = s.targetText || s.elementTag;
        return (
          <div className="flex items-center space-x-2">
            <span className="text-lg">⌨️</span>
            <span className="truncate">
              Input into <strong>{targetDescription}</strong>: "{s.value}"
            </span>
          </div>
        );
      }
      case "key_press": {
        const s = step as KeyPressStep;
        return (
          <div className="flex items-center space-x-2">
            <span className="text-lg">🔑</span>
            <span className="truncate">
              Press <strong>{s.key}</strong> on {s.elementTag || "document"}
            </span>
          </div>
        );
      }
      case "navigation": {
        const s = step as NavigationStep;
        return (
          <div className="flex items-center space-x-2">
            <span className="text-lg">🧭</span>
            <span className="truncate">Navigate: {s.url}</span>
          </div>
        );
      }
      case "scroll": {
        const s = step as ScrollStep;
        return (
          <div className="flex items-center space-x-2">
            <span className="text-lg">↕️</span>
            <span className="truncate">
              Scroll to ({s.scrollX}, {s.scrollY})
            </span>
          </div>
        );
      }
      default:
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        return <>{(step as any).type}</>; // Fallback
    }
  };

  // --- Step Detail Renderer (Collapsible section or part of card body) ---
  const renderStepDetailsContent = (step: Step) => {
    const baseInfo = (
      <>
        <p>
          <strong>Timestamp:</strong>{" "}
          {new Date(step.timestamp).toLocaleString()}
        </p>
        {step.url && (
          <p>
            <strong>URL:</strong> {step.url}
          </p>
        )}
        {/* Tab ID might be less relevant now, could remove */}
        {/* <p><strong>Tab ID:</strong> {step.tabId}</p> */}
      </>
    );

    let specificInfo = null;

    switch (step.type) {
      case "click":
      case "input":
      case "key_press": {
        const s = step as ClickStep | InputStep | KeyPressStep; // Union type
        specificInfo = (
          <>
            {(s as ClickStep | InputStep).frameUrl &&
              (s as ClickStep | InputStep).frameUrl !== s.url && (
                <p>
                  <strong>Frame URL:</strong>{" "}
                  {(s as ClickStep | InputStep).frameUrl}
                </p>
              )}
            {s.xpath && (
              <p>
                <strong>XPath:</strong> {s.xpath}
              </p>
            )}
            {s.cssSelector && (
              <p>
                <strong>CSS:</strong> {s.cssSelector}
              </p>
            )}
            {s.elementTag && (
              <p>
                <strong>Element:</strong> {s.elementTag}
              </p>
            )}
            {(s as ClickStep | InputStep).targetText && (
              <p>
                <strong>Target Text:</strong> {(s as ClickStep | InputStep).targetText}
              </p>
            )}
            {(s as ClickStep).radioButtonInfo && (
              <div>
                <p>
                  <strong>Field Name:</strong> {(s as ClickStep).radioButtonInfo?.fieldName}
                </p>
                <p>
                  <strong>Selected Option:</strong> {(s as ClickStep).radioButtonInfo?.optionValue}
                </p>
                <p>
                  <strong>All Options:</strong> {(s as ClickStep).radioButtonInfo?.allOptions?.join(', ')}
                </p>
              </div>
            )}
            {(s as ClickStep).elementText && (
              <p>
                <strong>Text:</strong> {(s as ClickStep).elementText}
              </p>
            )}
            {(s as InputStep).value && (
              <p>
                <strong>Value:</strong> {(s as InputStep).value}
              </p>
            )}
            {(s as KeyPressStep).key && (
              <p>
                <strong>Key:</strong> {(s as KeyPressStep).key}
              </p>
            )}
          </>
        );
        break;
      }
      case "navigation": {
        // Base info already has URL
        break;
      }
      case "scroll": {
        const s = step as ScrollStep;
        specificInfo = (
          <>
            <p>
              <strong>Target ID:</strong> {s.targetId}
            </p>
            <p>
              <strong>Scroll X:</strong> {s.scrollX}
            </p>
            <p>
              <strong>Scroll Y:</strong> {s.scrollY}
            </p>
          </>
        );
        break;
      }
      case "extract": {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const s = step as any; // ExtractStep type not imported
        specificInfo = (
          <>
            <p>
              <strong>Extraction Goal:</strong> {s.extractionGoal}
            </p>
          </>
        );
        break;
      }
      default:
        specificInfo = (
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          <p>Details not available for type: {(step as any).type}</p>
        );
    }

    return (
      <div className="text-[10px] text-muted-foreground break-all mt-2 space-y-1">
        {baseInfo}
        {specificInfo}
      </div>
    );
  };

      return (
      <div
        id={`event-item-${index}`} // Keep ID for potential scrolling
        onClick={onSelect}
        className={` 
          border rounded-lg mb-3 overflow-hidden cursor-pointer transition-all duration-150 ease-in-out 
          ${getStepBgColor(step, isSelected)}
          ${
            isSelected
              ? "shadow-md scale-[1.01]"
              : "hover:shadow-sm"
          } 
        `}
      >
      {/* Card Content using Flexbox */}
      <div className="flex items-start p-3 space-x-3">
        {/* Left side: Summary and Details */}
        <div className="flex-grow overflow-hidden">
          <div className="text-sm font-medium mb-2">
            {renderStepSummary(step)}
          </div>
          {renderStepDetailsContent(step)}
        </div>

        {/* Right side: Screenshot (if available) */}
        {canShowScreenshot && screenshot && (
          <div className="flex-shrink-0 w-24 h-auto border border-border rounded overflow-hidden shadow-sm ml-auto">
            <img
              src={screenshot}
              alt={`Screenshot for step ${index + 1}`}
              className="block w-full h-full object-cover"
              loading="lazy" // Lazy load screenshots further down
            />
          </div>
        )}
      </div>
    </div>
  );
};

// Main EventViewer component using the new card layout
export const EventViewer: React.FC = () => {
  const { workflow, currentEventIndex, selectEvent, recordingStatus } =
    useWorkflow();
  const steps = workflow?.steps || [];
  const scrollContainerRef = useRef<HTMLDivElement>(null); // Ref for the scrollable div

  // Effect to scroll selected card into view
  useEffect(() => {
    if (recordingStatus !== "recording") {
      // Only scroll selection when not recording
      const element = document.getElementById(
        `event-item-${currentEventIndex}`
      );
      element?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [currentEventIndex, recordingStatus]); // Add recordingStatus dependency

  // Effect to scroll to bottom when new steps are added during recording
  useEffect(() => {
    if (recordingStatus === "recording" && scrollContainerRef.current) {
      const { current: container } = scrollContainerRef;
      // Use setTimeout to allow DOM update before scrolling
      setTimeout(() => {
        container.scrollTop = container.scrollHeight;
        console.log("Scrolled to bottom due to new event during recording");
      }, 0);
    }
    // Depend on the number of steps and recording status
  }, [steps.length, recordingStatus]);

  if (!workflow || !workflow.steps || workflow.steps.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground p-6">
        No events recorded yet.
      </div>
    );
  }

  return (
    // Assign the ref to the scrollable container
    <div ref={scrollContainerRef} className="h-full overflow-y-auto p-0.5">
      {" "}
      {/* Single scrollable container */}
      {steps.map((step, index) => (
        <StepCard
          key={index}
          step={step}
          index={index}
          isSelected={index === currentEventIndex}
          onSelect={() => selectEvent(index)}
        />
      ))}
    </div>
  );
};
