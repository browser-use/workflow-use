import React, { useState, useMemo, useEffect, useRef } from 'react';
import { Globe, Search, Plus, Loader } from 'lucide-react';
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
} from '@/components/ui/sidebar';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { DeleteWorkflowDialog } from '@/components/DeleteWorkflowDialog';
import { WorkflowCategoryBlock } from '@/components/WorkflowCategoryBlock';
import { useAppContext } from '@/contexts/AppContext';
import { workflowService } from '@/services/workflowService';
import { useToast } from '@/hooks/use-toast';
import { EditRecordingDialog } from './EditRecordingDialog';
import { RecordingInProgressDialog } from './RecordingInProgressDialog';

type Category = 'today' | 'yesterday' | 'last-week' | 'last-month' | 'older';

export function WorkflowSidebar() {
  const [searchTerm, setSearchTerm] = useState('');
  const [deleteWorkflowId, setDeleteWorkflowId] = useState<string | null>(null);
  const { toast } = useToast();
  const {
    workflows,
    deleteWorkflow,
    sidebarStatus,
    checkForUnsavedChanges,
    recordingStatus,
    setRecordingStatus,
    recordingData,
    setRecordingData,
    activeDialog,
    setActiveDialog,
  } = useAppContext();

  // Important, this ref keeps track of the recording status
  const recordingStatusRef = useRef(recordingStatus);

  useEffect(() => {
    recordingStatusRef.current = recordingStatus;
    console.log('Recording status change:', recordingStatusRef.current);
  }, [recordingStatus]);

  const filteredWorkflows = useMemo(() => {
    if (!searchTerm) return workflows;
    return workflows.filter(
      (workflow) =>
        workflow.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        workflow.description.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [searchTerm, workflows]);

  const workflowsByCategory = useMemo(() => {
    const result: Record<Category, typeof workflows> = {
      today: [],
      yesterday: [],
      'last-week': [],
      'last-month': [],
      older: [],
    };

    const sorted = [...filteredWorkflows].sort((a, b) => {
      const getLatest = (wf: typeof a) =>
        Math.max(
          ...wf.steps
            .map((step) => step.timestamp || 0)
            .filter((ts) => ts !== null)
        );
      return getLatest(b) - getLatest(a);
    });

    sorted.forEach((workflow) => {
      const timestamps = workflow.steps
        .map((step) => step.timestamp)
        .filter((timestamp) => timestamp !== null);

      const mostRecentTimestamp =
        timestamps.length > 0 ? Math.max(...timestamps) : 0;

      const category = workflowService.getWorkflowCategory(
        mostRecentTimestamp
      ) as Category;

      if (category in result) {
        result[category].push(workflow);
      }
    });

    return result;
  }, [filteredWorkflows]);

  const handleRecordNewWorkflow = async () => {
    if (checkForUnsavedChanges()) {
      return;
    }
    setRecordingStatus('recording');
    try {
      const response = await workflowService.recordWorkflow();
      const refStatus = recordingStatusRef.current;
      if (refStatus === 'cancelling') {
        setActiveDialog(null);
        setRecordingData(null);
        setRecordingStatus('idle');
        return;
      }
      if (response?.success) {
        setRecordingData(response);
        setRecordingStatus('building');
        setActiveDialog('editRecording');
      } else {
        console.error('Recording failed:', response?.error);
        throw new Error(response?.error || 'Recording failed');
      }
    } catch (error) {
      console.error('Failed to record workflow:', error);
      setRecordingStatus('failed');
      toast({
        title: 'Recording Failed',
        description: 'Failed to record workflow. Please try again.',
        variant: 'destructive',
      });
    }
  };

  const handleDeleteWorkflow = (workflowId: string) => {
    if (checkForUnsavedChanges()) {
      return;
    }
    setDeleteWorkflowId(workflowId);
  };

  const confirmDeleteWorkflow = async (workflowId: string) => {
    if (!workflowId) return;
    try {
      await deleteWorkflow(workflowId);
    } catch (error) {
      console.error('Failed to delete workflow:', error);
    } finally {
      setDeleteWorkflowId(null);
    }
  };

  const handleCancelRecording = async () => {
    try {
      setRecordingStatus('cancelling');
      const response = await workflowService.stopRecording();
      if (response?.success) {
        setRecordingData(null);
        toast({
          title: '🎥 Recording Cancelled',
          description: 'The workflow recording has been cancelled.',
        });
      } else {
        throw new Error(response?.error || 'Failed to cancel recording');
      }
    } catch (error) {
      console.error('Failed to cancel recording:', error);
      setRecordingStatus('recording');
      toast({
        title: '⚠️ Error',
        description: 'Failed to cancel the recording. Please try again.',
      });
    }
  };

  const handleContinueRecording = () => {
    setActiveDialog(null);
  };

  const renderSidebarContent = () => {
    if (sidebarStatus === 'loading') {
      return (
        <div className="flex flex-col items-center justify-center p-8 space-y-4">
          <Globe className="w-8 h-8 text-purple-600 animate-bounce" />
          <p className="text-gray-600 animate-pulse">Loading workflows...</p>
        </div>
      );
    }

    if (sidebarStatus === 'error') {
      return (
        <div className="p-6 text-center text-red-500 bg-white shadow-md rounded-lg">
          <p className="text-base font-semibold text-black">
            Failed to load workflows. Try again by refreshing the page.
          </p>
          <p className="text-base font-semibold text-black">
            Make sure the server is running.
          </p>
        </div>
      );
    }

    return (
      <>
        <WorkflowCategoryBlock
          label="Today"
          workflows={workflowsByCategory.today}
          onDeleteWorkflow={handleDeleteWorkflow}
        />
        <WorkflowCategoryBlock
          label="Yesterday"
          workflows={workflowsByCategory.yesterday}
          onDeleteWorkflow={handleDeleteWorkflow}
        />
        <WorkflowCategoryBlock
          label="Last Week"
          workflows={workflowsByCategory['last-week']}
          onDeleteWorkflow={handleDeleteWorkflow}
        />
        <WorkflowCategoryBlock
          label="Last Month"
          workflows={workflowsByCategory['last-month']}
          onDeleteWorkflow={handleDeleteWorkflow}
        />
        <WorkflowCategoryBlock
          label="Older"
          workflows={workflowsByCategory.older}
          onDeleteWorkflow={handleDeleteWorkflow}
        />

        {filteredWorkflows.length === 0 && (
          <div className="p-4 text-center text-gray-500">
            No workflows found matching "{searchTerm}"
          </div>
        )}
      </>
    );
  };

  return (
    <>
      <Sidebar className="w-[25%] border-r border-gray-200">
        <SidebarHeader className="border-b border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-purple-500 to-blue-600 rounded-lg">
              <Globe className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-gray-900">
                browser-use
              </h1>
              <p className="text-sm text-gray-500">Workflow Studio</p>
            </div>
          </div>

          <div className="mt-4 relative">
            <Input
              placeholder="Search workflows..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8"
            />
            <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-500" />
          </div>

          <Button
            onClick={handleRecordNewWorkflow}
            disabled={recordingStatus === 'recording'}
            className="mt-4 w-full bg-purple-600 hover:bg-purple-700 text-white"
          >
            {recordingStatus === 'recording' ? (
              <>
                <Loader className="w-4 h-4 mr-2 animate-spin" />
                Recording...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4 mr-2" />
                Record New Workflow
              </>
            )}
          </Button>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu className="space-y-1">
                {renderSidebarContent()}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>

      <DeleteWorkflowDialog
        workflowId={deleteWorkflowId}
        onConfirm={confirmDeleteWorkflow}
        onCancel={() => setDeleteWorkflowId(null)}
      />

      {activeDialog === 'editRecording' && recordingData && (
        <EditRecordingDialog
          isOpen={true}
          onClose={() => {
            setActiveDialog(null);
            setRecordingData(null);
          }}
          recordingData={recordingData}
        />
      )}

      {activeDialog === 'recordingInProgress' && (
        <RecordingInProgressDialog
          onCancel={handleCancelRecording}
          onContinue={handleContinueRecording}
          recordingStatus={recordingStatus}
        />
      )}
    </>
  );
}
