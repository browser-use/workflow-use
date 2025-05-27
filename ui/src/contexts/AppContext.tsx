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
import { useToast } from '@/hooks/use-toast';

export type DisplayMode = 'canvas' | 'editor' | 'log' | 'start';
export type DialogType =
  | 'run'
  | 'runAsTool'
  | 'unsavedChanges'
  | 'editRecording'
  | 'recordingInProgress'
  | null;
export type SidebarStatus = 'loading' | 'ready' | 'error';
export type EditorStatus = 'saved' | 'unsaved';
export type WorkflowStatus = 'idle' | 'running' | 'failed' | 'cancelling';
export type RecordingStatus = 'idle' | 'recording' | 'building' | 'failed';

interface AppContextType {
  displayMode: DisplayMode;
  setDisplayMode: (mode: DisplayMode) => void;
  workflowStatus: WorkflowStatus;
  workflowError: string | null;
  currentTaskId: number | null;
  currentLogPosition: number;
  sidebarStatus: SidebarStatus;
  editorStatus: EditorStatus;
  setEditorStatus: (status: EditorStatus) => void;
  currentWorkflowData: Workflow | null;
  workflows: Workflow[];
  addWorkflow: (workflow: Workflow) => void;
  deleteWorkflow: (workflowId: string) => void;
  selectWorkflow: (workflowName: string) => void;
  activeDialog: DialogType;
  setActiveDialog: (dialog: DialogType) => void;
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
  checkForUnsavedChanges: () => boolean;
  recordingStatus: RecordingStatus;
  setRecordingStatus: (status: RecordingStatus) => void;
  recordingData: any;
  setRecordingData: (data: any) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const { toast } = useToast();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [displayMode, setDisplay] = useState<DisplayMode>('start');
  const [currentWorkflowData, setCurrentWorkflowData] =
    useState<Workflow | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus>('idle');
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [activeDialog, setActiveDialog] = useState<DialogType>(null);
  const [sidebarStatus, setSidebarStatus] = useState<SidebarStatus>('loading');
  const [editorStatus, setEditorStatus] = useState<EditorStatus>('saved');
  const [logData, setLogData] = useState<string[]>([]);
  const [logPosition, setLogPosition] = useState<number>(0);
  const [currentTaskId, setCurrentTaskId] = useState<number | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const [recordingStatus, setRecordingStatus] =
    useState<RecordingStatus>('idle');
  const [recordingData, setRecordingData] = useState<any>(null);

  const checkForUnsavedChanges = useCallback(() => {
    if (recordingStatus === 'recording') {
      setActiveDialog('recordingInProgress');
      return true;
    }
    if (editorStatus === 'unsaved') {
      setActiveDialog('unsavedChanges');
      return true;
    }
    return false;
  }, [editorStatus, recordingStatus, setActiveDialog]);

  const selectWorkflow = useCallback(
    (workflowName: string) => {
      if (checkForUnsavedChanges()) {
        return;
      }
      const wf = workflows.find((w) => w.name === workflowName);
      if (wf) {
        setCurrentWorkflowData(wf);
      } else {
        setCurrentWorkflowData(null); // fallback
      }
    },
    [workflows, checkForUnsavedChanges]
  );

  const addWorkflow = async (workflow: Workflow) => {
    try {
      await workflowService.addWorkflow(
        workflow.name,
        JSON.stringify(workflow)
      );
      setWorkflows((prev) => [workflow, ...prev]);
      toast({
        title: 'Workflow added! ✅',
        description: 'The workflow has been successfully added!',
      });
    } catch (err) {
      console.error('Failed to add workflow:', err);
      toast({
        title: 'Error ❌',
        description: 'Failed to add the workflow. Please try again! 🔄',
      });
    }
  };

  const deleteWorkflow = async (workflowName: string) => {
    try {
      await workflowService.deleteWorkflow(workflowName);
      setWorkflows((prev) => prev.filter((wf) => wf.name !== workflowName));
      toast({
        title: 'Workflow deleted! ✅',
        description: 'The workflow has been successfully deleted!',
      });
    } catch (err) {
      console.error('Failed to delete workflow:', err);
      toast({
        title: 'Error ❌',
        description: 'Failed to delete the workflow. Please try again! 🔄',
      });
    }
  };

  const updateWorkflow = useCallback(
    async (oldWorkflow: Workflow, newWorkflow: Workflow) => {
      try {
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
        if (
          JSON.stringify(oldWorkflow.steps) !==
          JSON.stringify(newWorkflow.steps)
        ) {
          newWorkflow.steps.forEach((newStep, index) => {
            const oldStep = oldWorkflow.steps[index];
            if (JSON.stringify(oldStep) !== JSON.stringify(newStep)) {
              workflowService.updateWorkflow(newWorkflow.name, index, newStep);
            }
          });
        }
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
            setWorkflowStatus(data.status as WorkflowStatus);
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

      setWorkflowError(null);
      setCurrentTaskId(null);
      setLogPosition(0);
      setWorkflowStatus('idle');

      try {
        const result = await workflowService.executeWorkflow(name, inputFields);
        setCurrentTaskId(parseInt(result.taskId));
        setLogPosition(result.logPosition);
        setWorkflowStatus('running');
        setDisplayMode('log');

        startPollingLogs(result.taskId);
      } catch (err) {
        console.error('Failed to execute workflow:', err);
        setWorkflowError('An error occurred while executing the workflow');
        setWorkflowStatus('failed');
      }
    },
    [startPollingLogs, checkForUnsavedChanges]
  );

  useEffect(() => {
    const logInterval = setInterval(() => {
      console.log('Current workflows:', workflows);
      console.log('Current workflow data:', currentWorkflowData);
    }, 2000); // Log every 10 seconds

    return () => clearInterval(logInterval);
  }, [workflows, currentWorkflowData]);

  // Fetch workflows on mount
  useEffect(() => {
    const fetchWorkflows = async () => {
      try {
        setSidebarStatus('loading');
        const response = await workflowService.getWorkflows();
        const parsedWorkflows = response.map((wf: any) => JSON.parse(wf));
        setWorkflows(parsedWorkflows);
        setSidebarStatus('ready');
      } catch (err) {
        console.error('Failed to fetch workflows:', err);
        setSidebarStatus('error');
      }
    };
    fetchWorkflows();
  }, []);

  const setDisplayMode = useCallback(
    (mode: DisplayMode) => {
      if (checkForUnsavedChanges()) {
        return;
      }
      setDisplay(mode);
    },
    [checkForUnsavedChanges]
  );

  return (
    <AppContext.Provider
      value={{
        selectWorkflow,
        displayMode,
        setDisplayMode,
        workflowStatus,
        workflowError,
        currentTaskId,
        currentLogPosition: logPosition,
        currentWorkflowData,
        workflows,
        addWorkflow,
        deleteWorkflow,
        activeDialog,
        setActiveDialog,
        executeWorkflow,
        updateWorkflow,
        startPollingLogs,
        stopPollingLogs,
        logData,
        cancelWorkflowExecution,
        sidebarStatus,
        editorStatus,
        setEditorStatus,
        checkForUnsavedChanges,
        recordingStatus,
        setRecordingStatus,
        recordingData,
        setRecordingData,
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
