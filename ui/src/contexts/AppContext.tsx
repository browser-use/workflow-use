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

import governmentFormSubmission from '@/data/workflows/government-form-submission.json';
import loginFlow from '@/data/workflows/login-flow.json';
import formSubmission from '@/data/workflows/form-submission.json';
import dataExtraction from '@/data/workflows/data-extraction.json';
import navigationTest from '@/data/workflows/navigation-test.json';

import { Workflow, WorkflowMetadata } from '../types/workflow-layout.types';
import { WorkflowServiceImpl } from '@/services/workflowService';
import { fetchWorkflowLogs, cancelWorkflow } from '@/services/pollingService';
import { InputField } from '@/types/play-button.types';

const workflowService = new WorkflowServiceImpl();

export type DisplayMode = 'canvas' | 'editor' | 'log';

interface AppContextType {
  displayMode: DisplayMode;
  setDisplayMode: (mode: DisplayMode) => void;
  workflowStatus: string;
  workflowError: string | null;
  isWorkflowRunning: boolean;
  currentTaskId: string | null;
  currentLogPosition: number;

  currentWorkflowData: Workflow | null;
  workflows: Workflow[];
  selectedWorkflow: string | null;
  addWorkflow: (workflow: Workflow) => void;
  deleteWorkflow: (workflowId: string) => void;
  selectWorkflow: (workflowName: string) => void;

  showRunDialog: boolean;
  setShowRunDialog: (show: boolean) => void;

  showRunAsToolDialog: boolean;
  setShowRunAsToolDialog: (show: boolean) => void;

  searchWorkflows: (term: string) => Workflow[];
  executeWorkflow: (name: string, inputFields: InputField[]) => Promise<void>;

  fetchWorkflowAndSet: (name: string) => Promise<void>;
  updateMetadata: (name: string, metadata: WorkflowMetadata) => Promise<void>;
  startPollingLogs: (taskId: string) => void;
  stopPollingLogs: () => void;
  logData: string[];
  cancelWorkflowExecution: (taskId: string) => Promise<void>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

interface AppProviderProps {
  children: ReactNode;
}

const defaultWorkflows: Workflow[] = [
  governmentFormSubmission as Workflow,
  loginFlow as Workflow,
  formSubmission as Workflow,
  dataExtraction as Workflow,
  navigationTest as Workflow,
];

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const [workflows, setWorkflows] = useState<Workflow[]>(defaultWorkflows);
  const [selectedWorkflow, setSelectedWorkflow] = useState<string | null>(null);
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
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const selectWorkflow = (workflowName: string) => {
    setSelectedWorkflow(workflowName);

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

  const fetchWorkflowAndSet = useCallback(async (name: string) => {
    try {
      const workflow = await workflowService.getWorkflow(name);
      setSelectedWorkflow(name);
      setCurrentWorkflowData(workflow);
    } catch (err) {
      console.error(`Failed to load workflow: ${name}`, err);
    }
  }, []);

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
        setCurrentTaskId(result.taskId);
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

  return (
    <AppContext.Provider
      value={{
        selectedWorkflow,
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
        searchWorkflows,
        executeWorkflow,
        fetchWorkflowAndSet,
        updateMetadata,
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
