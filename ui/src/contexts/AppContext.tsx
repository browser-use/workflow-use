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
import { Workflow } from '../types/workflow-layout.types';
import { workflowService } from '@/services/workflowService';
import { fetchWorkflowLogs, cancelWorkflow } from '@/services/pollingService';
import { inputFieldSchema } from '../types/workflow-layout.types';
import { z } from 'zod';

export type DisplayMode = 'canvas' | 'editor' | 'log' | 'start';

interface AppContextType {
  displayMode: DisplayMode;
  setDisplayMode: (mode: DisplayMode) => void;
  workflowStatus: string;
  workflowError: string | null;
  isWorkflowRunning: boolean;
  currentTaskId: number | null;
  currentLogPosition: number;
  isLoadingWorkflows: boolean;

  currentWorkflowData: Workflow | null;
  workflows: Workflow[];
  addWorkflow: (workflow: Workflow) => void;
  deleteWorkflow: (workflowId: string) => void;
  selectWorkflow: (workflowName: string) => void;

  showRunDialog: boolean;
  setShowRunDialog: (show: boolean) => void;

  showRunAsToolDialog: boolean;
  setShowRunAsToolDialog: (show: boolean) => void;

  executeWorkflow: (
    name: string,
    inputFields: z.infer<typeof inputFieldSchema>[]
  ) => Promise<void>;

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
  const [displayMode, setDisplayMode] = useState<DisplayMode>('start');
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
  const [isLoadingWorkflows, setIsLoadingWorkflows] = useState(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const selectWorkflow = (workflowName: string) => {
    const wf = workflows.find((w) => w.name === workflowName);
    if (wf) {
      setCurrentWorkflowData(wf);
    } else {
      setCurrentWorkflowData(null); // fallback
    }
  };

  const addWorkflow = async (workflow: Workflow) => {
    try {
      await workflowService.addWorkflow(
        workflow.name,
        JSON.stringify(workflow)
      );
      setWorkflows((prev) => [workflow, ...prev]);
    } catch (err) {
      console.error('Failed to add workflow:', err);
    }
  };

  const deleteWorkflow = async (workflowName: string) => {
    try {
      await workflowService.deleteWorkflow(workflowName);
      setWorkflows((prev) => prev.filter((wf) => wf.name !== workflowName));
    } catch (err) {
      console.error('Failed to delete workflow:', err);
    }
  };

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
    async (name: string, inputFields: z.infer<typeof inputFieldSchema>[]) => {
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
        setIsLoadingWorkflows(true);
        const response = await workflowService.getWorkflows();
        const parsedWorkflows = response.map((wf: any) => JSON.parse(wf));
        setWorkflows(parsedWorkflows);
      } catch (err) {
        console.error('Failed to fetch workflows:', err);
      } finally {
        setIsLoadingWorkflows(false);
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
        workflows,
        addWorkflow,
        deleteWorkflow,
        showRunDialog,
        setShowRunDialog,
        showRunAsToolDialog,
        setShowRunAsToolDialog,
        executeWorkflow,
        updateWorkflow,
        startPollingLogs,
        stopPollingLogs,
        logData,
        cancelWorkflowExecution,
        isLoadingWorkflows,
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
