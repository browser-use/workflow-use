import React, {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { Workflow } from "../../../lib/workflow-types"; // Adjust path as needed

type WorkflowState = {
  workflow: Workflow | null;
  recordingStatus: string; // e.g., 'idle', 'recording', 'stopped', 'error'
  currentEventIndex: number;
  isLoading: boolean;
  error: string | null;
};

type WorkflowContextType = WorkflowState & {
  startRecording: () => void;
  stopRecording: () => void;
  discardAndStartNew: () => void;
  selectEvent: (index: number) => void;
  fetchWorkflowData: (isPolling?: boolean) => void; // Add optional flag
};

const WorkflowContext = createContext<WorkflowContextType | undefined>(
  undefined
);

interface WorkflowProviderProps {
  children: ReactNode;
}

const POLLING_INTERVAL = 2000; // Fetch every 2 seconds during recording

export const WorkflowProvider: React.FC<WorkflowProviderProps> = ({
  children,
}) => {
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [recordingStatus, setRecordingStatus] = useState<string>("idle"); // 'idle', 'recording', 'stopped', 'error'
  const [currentEventIndex, setCurrentEventIndex] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchWorkflowData = useCallback(async (isPolling: boolean = false) => {
    if (!isPolling) {
      setIsLoading(true);
    }
    try {
      const data = await chrome.runtime.sendMessage({
        type: "GET_RECORDING_DATA",
      });
      console.log(
        "Received workflow data from background (polling=" + isPolling + "):",
        data
      );
      if (data && data.workflow && data.recordingStatus) {
        // Always update workflow when fetching (polling or not)
        setWorkflow(data.workflow);

        // If NOT polling, update status and index based on fetched data
        // If polling, we primarily rely on the broadcast message for status changes
        if (!isPolling) {
          setRecordingStatus(data.recordingStatus);
          setCurrentEventIndex(
            data.workflow.steps ? data.workflow.steps.length - 1 : 0
          );
        } else {
          // If polling, ensure index is valid (e.g., after step deletion)
          // Only adjust index based on current workflow state from polling
          setCurrentEventIndex((prevIndex) =>
            Math.min(prevIndex, (data.workflow.steps?.length || 1) - 1)
          );
          // Do NOT set recordingStatus from polling fetch, wait for broadcast message
        }
        // Clear error on successful fetch
        setError(null);
      } else {
        console.warn(
          "Received invalid/incomplete data structure from GET_RECORDING_DATA"
        );
        if (!isPolling) {
          setWorkflow(null);
          setRecordingStatus("idle");
          setCurrentEventIndex(0);
        }
      }
    } catch (err) {
      console.error(
        "Error fetching workflow data (polling=" + isPolling + "):",
        err
      );
      // Only set error state if it wasn't a background poll error
      // and the status isn't already error
      if (!isPolling) {
        const errorMessage = err instanceof Error ? err.message : String(err);
        setError(`Failed to load workflow data: ${errorMessage}`);
        setRecordingStatus("error");
        setWorkflow(null);
      }
    } finally {
      if (!isPolling) {
        setIsLoading(false);
      }
    }
    // Remove state dependencies to stabilize the function reference
  }, []);

  useEffect(() => {
    // Initial fetch on mount
    fetchWorkflowData(false);

    // Listener for status updates pushed from the background script
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const messageListener = (message: any, _sender: any, _sendResponse: any) => {
      console.log("Sidepanel received message:", message);
      if (message.type === "recording_status_updated") {
        console.log(
          "Recording status updated message received:",
          message.payload
        );
        const newStatus = message.payload.status;
        // Use functional update to get previous status reliably
        setRecordingStatus((prevStatus) => {
          // If status changed from non-stopped/idle to stopped or idle, fetch final data
          if (
            newStatus !== prevStatus &&
            (newStatus === "stopped" || newStatus === "idle")
          ) {
            fetchWorkflowData(false); // Fetch final data, show loading
          }
          return newStatus; // Return the new status to update the state
        });
      }
    };
    chrome.runtime.onMessage.addListener(messageListener);

    // --- Polling Logic ---
    let pollingIntervalId: NodeJS.Timeout | null = null;
    if (recordingStatus === "recording") {
      pollingIntervalId = setInterval(() => {
        fetchWorkflowData(true); // Fetch updates in the background (polling)
      }, POLLING_INTERVAL);
      console.log(`Polling started (Interval ID: ${pollingIntervalId})`);
    }
    // --- End Polling Logic ---

    // Cleanup listener and interval
    return () => {
      chrome.runtime.onMessage.removeListener(messageListener);
      if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
        console.log(
          `Polling stopped (Cleared Interval ID: ${pollingIntervalId})`
        );
      }
    };
    // Keep dependencies: fetchWorkflowData is stable now,
    // recordingStatus dependency correctly handles interval setup/teardown.
  }, [fetchWorkflowData, recordingStatus]);

  // startRecording, stopRecording, discardAndStartNew, selectEvent remain largely the same
  // but ensure isLoading is handled appropriately
  const startRecording = useCallback(() => {
    setError(null);
    setIsLoading(true);
    chrome.runtime.sendMessage({ type: "START_RECORDING" }, (_response) => {
      // Loading state will be turned off by the fetchWorkflowData triggered
      // by the recording_status_updated message, or on error here.
      if (chrome.runtime.lastError) {
        console.error("Error starting recording:", chrome.runtime.lastError);
        setError(
          `Failed to start recording: ${chrome.runtime.lastError.message}`
        );
        setRecordingStatus("error");
        setIsLoading(false); // Stop loading on error
      } else {
        console.log("Start recording acknowledged by background.");
        // State updates happen via broadcast + fetch
      }
    });
  }, []); // No dependencies needed

  const stopRecording = useCallback(() => {
    setError(null);
    setIsLoading(true);
    chrome.runtime.sendMessage({ type: "STOP_RECORDING" }, (_response) => {
      // Loading state will be turned off by the fetchWorkflowData triggered
      // by the recording_status_updated message, or on error here.
      if (chrome.runtime.lastError) {
        console.error("Error stopping recording:", chrome.runtime.lastError);
        setError(
          `Failed to stop recording: ${chrome.runtime.lastError.message}`
        );
        setRecordingStatus("error");
        setIsLoading(false); // Stop loading on error
      } else {
        console.log("Stop recording acknowledged by background.");
        // State updates happen via broadcast + fetch
      }
    });
  }, []); // No dependencies needed

  const discardAndStartNew = useCallback(() => {
    startRecording();
  }, [startRecording]);

  const selectEvent = useCallback((index: number) => {
    setCurrentEventIndex(index);
  }, []);

  const value = {
    workflow,
    recordingStatus,
    currentEventIndex,
    isLoading,
    error,
    startRecording,
    stopRecording,
    discardAndStartNew,
    selectEvent,
    fetchWorkflowData,
  };

  return (
    <WorkflowContext.Provider value={value}>
      {children}
    </WorkflowContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useWorkflow = (): WorkflowContextType => {
  const context = useContext(WorkflowContext);
  if (context === undefined) {
    throw new Error("useWorkflow must be used within a WorkflowProvider");
  }
  return context;
};
