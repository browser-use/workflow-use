import React, { useState, useMemo } from 'react';
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
import { getUniqueWorkflowName } from '@/lib/utils';
import { workflowService } from '@/services/workflowService';

export function WorkflowSidebar() {
  const [searchTerm, setSearchTerm] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [deleteWorkflowId, setDeleteWorkflowId] = useState<string | null>(null);
  const { workflows, addWorkflow, deleteWorkflow, isLoadingWorkflows } =
    useAppContext();

  const filteredWorkflows = useMemo(() => {
    if (!searchTerm) return workflows;
    return workflows.filter(
      (workflow) =>
        workflow.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        workflow.description.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [searchTerm, workflows]);

  const workflowsByCategory = useMemo(() => {
    type Category =
      | 'today'
      | 'yesterday'
      | 'last-week'
      | 'last-month'
      | 'older';
    const result: Record<Category, typeof workflows> = {
      today: [],
      yesterday: [],
      'last-week': [],
      'last-month': [],
      older: [],
    };

    filteredWorkflows.forEach((workflow) => {
      // Find the most recent timestamp from workflow steps
      const timestamps = workflow.steps
        .map((step) => step.timestamp)
        .filter((timestamp) => timestamp !== null);

      const mostRecentTimestamp =
        timestamps.length > 0 ? Math.max(...timestamps) : 0; // Use 0 if no timestamps found

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
    setIsRecording(true);
    console.log('Recording new workflow...');

    // Simulate recording time
    await new Promise((resolve) => setTimeout(resolve, 3000));

    // Add a random workflow from existing ones as a duplicate
    const random = workflows[Math.floor(Math.random() * workflows.length)];

    if (!random) {
      console.error('No workflows available to duplicate');
      setIsRecording(false);
      return;
    }

    const newWorkflow = {
      ...random,
      name: getUniqueWorkflowName(
        `${random.name}`,
        workflows.map((wf) => wf.name)
      ),
      workflow_analysis: random.workflow_analysis,
      description: random.description,
      version: random.version,
      steps: random.steps,
      input_schema: random.input_schema,
    };

    addWorkflow(newWorkflow);
    console.log('Workflow recording completed!');
    setIsRecording(false);
  };

  const handleDeleteWorkflow = (workflowId: string) => {
    setDeleteWorkflowId(workflowId);
  };

  const confirmDeleteWorkflow = (workflowId: string) => {
    if (!workflowId) return;
    console.log('Deleting workflow:', workflowId);
    deleteWorkflow(workflowId);
    setDeleteWorkflowId(null);
  };

  const cancelDeleteWorkflow = () => {
    setDeleteWorkflowId(null);
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
            disabled={isRecording}
            className="mt-4 w-full bg-purple-600 hover:bg-purple-700 text-white"
          >
            {isRecording ? (
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
                {isLoadingWorkflows ? (
                  <div className="flex items-center justify-center p-8">
                    <Loader className="w-6 h-6 animate-spin text-purple-600" />
                  </div>
                ) : (
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
                )}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>

      <DeleteWorkflowDialog
        workflowId={deleteWorkflowId}
        onConfirm={confirmDeleteWorkflow}
        onCancel={cancelDeleteWorkflow}
      />
    </>
  );
}
