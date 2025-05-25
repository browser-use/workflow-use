import React, {
  createContext,
  useContext,
  useState,
  useMemo,
  ReactNode,
  useCallback,
  useRef,
  useEffect,
} from 'react';
import { Workflow, WorkflowMetadata } from '../types/workflow-layout.types';
import { workflowService } from '@/services/workflowService';
import { fetchWorkflowLogs, cancelWorkflow } from '@/services/pollingService';
import { InputField } from '@/types/play-button.types';

export type DisplayMode = 'canvas' | 'editor' | 'log';

interface AppContextType {
  displayMode: DisplayMode;
  setDisplayMode: (mode: DisplayMode) => void;
  workflowStatus: string;
  workflowError: string | null;
  isWorkflowRunning: boolean;
  currentTaskId: number | null;
  currentLogPosition: number;

  currentWorkflowData: Workflow | null;
  setCurrentWorkflowData: (workflow: Workflow | null) => void;
  workflows: Workflow[];
  addWorkflow: (workflow: Workflow) => void;
  deleteWorkflow: (workflowId: string) => void;
  selectWorkflow: (workflowName: string) => void;

  showRunDialog: boolean;
  setShowRunDialog: (show: boolean) => void;

  showRunAsToolDialog: boolean;
  setShowRunAsToolDialog: (show: boolean) => void;

  searchWorkflows: (term: string) => Workflow[];
  executeWorkflow: (name: string, inputFields: InputField[]) => Promise<void>;

  updateMetadata: (name: string, metadata: WorkflowMetadata) => Promise<void>;
  updateWorkflow: (
    oldWorkflow: Workflow,
    newWorkflow: Workflow
  ) => Promise<void>;
  startPollingLogs: (taskId: string) => void;
  stopPollingLogs: () => void;
  logData: string[];
  cancelWorkflowExecution: (taskId: string) => Promise<void>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [displayMode, setDisplayMode] = useState<DisplayMode>('canvas');
  const [currentWorkflowData, setCurrentWorkflowData] =
    useState<Workflow | null>(null);
  const [showRunDialog, setShowRunDialog] = useState(false);
  const [showRunAsToolDialog, setShowRunAsToolDialog] = useState(false);
  const [logData, setLogData] = useState<string[]>([]);
  const [workflowStatus, setWorkflowStatus] = useState<string>('idle');
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [isWorkflowRunning, setIsWorkflowRunning] = useState(false);
  const [logPosition, setLogPosition] = useState<number>(0);
  const [currentTaskId, setCurrentTaskId] = useState<number | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const selectWorkflow = (workflowName: string) => {
    const wf = workflows.find((w) => w.name === workflowName);
    if (wf) {
      setCurrentWorkflowData(wf);
    } else {
      setCurrentWorkflowData(null); // fallback
    }
  };

  const addWorkflow = (workflow: Workflow) => {
    // TODO: Implement add workflow
    setWorkflows((prev) => [workflow, ...prev]);
  };

  const deleteWorkflow = (workflowName: string) => {
    // TODO: Implement delete workflow
    setWorkflows((prev) => prev.filter((wf) => wf.name !== workflowName));
  };

  const searchWorkflows = (term: string) => {
    const lower = term.toLowerCase();
    return workflows.filter(
      (wf) =>
        wf.name.toLowerCase().includes(lower) ||
        wf.description.toLowerCase().includes(lower)
    );
  };

  const updateMetadata = useCallback(
    async (name: string, metadata: WorkflowMetadata) => {
      try {
        await workflowService.updateWorkflowMetadata(name, metadata);

        if (currentWorkflowData?.name === name) {
          setCurrentWorkflowData({ ...currentWorkflowData, ...metadata });
        }
      } catch (err) {
        console.error(`Failed to update metadata for ${name}`, err);
      }
    },
    [currentWorkflowData]
  );

  const updateWorkflow = useCallback(
    async (oldWorkflow: Workflow, newWorkflow: Workflow) => {
      try {
        // Update metadata if it changed
        if (
          oldWorkflow.name !== newWorkflow.name ||
          oldWorkflow.description !== newWorkflow.description ||
          oldWorkflow.version !== newWorkflow.version ||
          JSON.stringify(oldWorkflow.input_schema) !==
            JSON.stringify(newWorkflow.input_schema)
        ) {
          await workflowService.updateWorkflowMetadata(newWorkflow.name, {
            name: newWorkflow.name,
            description: newWorkflow.description,
            version: newWorkflow.version,
            input_schema: newWorkflow.input_schema,
          });
        }

        // Update steps if they changed
        if (
          JSON.stringify(oldWorkflow.steps) !==
          JSON.stringify(newWorkflow.steps)
        ) {
          // Find changed steps
          newWorkflow.steps.forEach((newStep, index) => {
            const oldStep = oldWorkflow.steps[index];
            if (JSON.stringify(oldStep) !== JSON.stringify(newStep)) {
              workflowService.updateWorkflow(newWorkflow.name, index, newStep);
            }
          });
        }

        // Update local state
        setWorkflows((prev) =>
          prev.map((wf) => (wf.name === oldWorkflow.name ? newWorkflow : wf))
        );

        if (currentWorkflowData?.name === oldWorkflow.name) {
          setCurrentWorkflowData(newWorkflow);
        }
      } catch (err) {
        console.error(`Failed to update workflow ${oldWorkflow.name}`, err);
        throw err;
      }
    },
    [currentWorkflowData]
  );

  const stopPollingLogs = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPollingLogs = useCallback(
    (taskId: string) => {
      stopPollingLogs(); // clear any existing polling

      const poll = async () => {
        try {
          const data = await fetchWorkflowLogs(taskId, logPosition);

          if (data.logs?.length) {
            setLogData((prev) => [...prev, ...data.logs]);
          }

          setLogPosition(data.log_position);

          if (data.status && data.status !== workflowStatus) {
            setWorkflowStatus(data.status);
            if (data.status === 'failed' && data.error) {
              setWorkflowError(data.error);
            }
          }
        } catch (err) {
          console.error('Polling error:', err);
        }
      };

      poll();

      pollingRef.current = setInterval(() => {
        poll();
      }, 2000);
    },
    [logPosition, workflowStatus, stopPollingLogs]
  );

  const cancelWorkflowExecution = async (taskId: string) => {
    try {
      await cancelWorkflow(taskId);
      setWorkflowStatus('cancelling');
    } catch (err) {
      console.error('Failed to cancel workflow:', err);
      // optionally: set error state
    }
  };

  const executeWorkflow = useCallback(
    async (name: string, inputFields: InputField[]) => {
      if (!name) return;

      // Validate required inputs
      const missingInputs = inputFields.filter(
        (field) => field.required && !field.value
      );
      if (missingInputs.length > 0) {
        setWorkflowError(
          `Missing required inputs: ${missingInputs
            .map((f) => f.name)
            .join(', ')}`
        );
        return;
      }

      // Reset state
      setIsWorkflowRunning(true);
      setWorkflowError(null);
      setCurrentTaskId(null);
      setLogPosition(0);
      setWorkflowStatus('idle');

      try {
        const result = await workflowService.executeWorkflow(name, inputFields);
        setCurrentTaskId(parseInt(result.taskId));
        setLogPosition(result.logPosition);
        setIsWorkflowRunning(true);
        setWorkflowStatus('running');
        setDisplayMode('log');

        // Start polling for logs
        startPollingLogs(result.taskId);
      } catch (err) {
        console.error('Failed to execute workflow:', err);
        setWorkflowError('An error occurred while executing the workflow');
        setWorkflowStatus('failed');
      }
    },
    [startPollingLogs]
  );

  useEffect(() => {
    const logInterval = setInterval(() => {
      console.log('Current workflows:', workflows);
      console.log('Current workflow data:', currentWorkflowData);
    }, 10000); // Log every 10 seconds

    return () => clearInterval(logInterval);
  }, [workflows, currentWorkflowData]);

  // Fetch workflows on mount
  useEffect(() => {
    const fetchWorkflows = async () => {
      try {
        console.log('Set here a loading state to sidebar');
        const response = await workflowService.getWorkflows();
        const parsedWorkflows = response.map((wf: string) => JSON.parse(wf));
        setWorkflows(parsedWorkflows);
      } catch (err) {
        console.error('Failed to fetch workflows:', err);
      }
    };
    fetchWorkflows();
  }, []);

  return (
    <AppContext.Provider
      value={{
        selectWorkflow,
        displayMode,
        setDisplayMode,
        workflowStatus,
        workflowError,
        isWorkflowRunning,
        currentTaskId,
        currentLogPosition: logPosition,
        currentWorkflowData,
        setCurrentWorkflowData,
        workflows,
        addWorkflow,
        deleteWorkflow,
        showRunDialog,
        setShowRunDialog,
        showRunAsToolDialog,
        setShowRunAsToolDialog,
        searchWorkflows,
        executeWorkflow,
        updateMetadata,
        updateWorkflow,
        startPollingLogs,
        stopPollingLogs,
        logData,
        cancelWorkflowExecution,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};
