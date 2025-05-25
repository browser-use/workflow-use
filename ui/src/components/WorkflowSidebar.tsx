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
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { DeleteWorkflowDialog } from '@/components/DeleteWorkflowDialog';
import { WorkflowItem } from '@/components/WorkflowItem';
import { WorkflowCategoryBlock } from '@/components/WorkflowCategoryBlock';
import { useAppContext } from '@/contexts/AppContext';
import { getUniqueWorkflowName } from '@/lib/utils';
import { workflowService } from '@/services/workflowService';

export function WorkflowSidebar() {
  const [searchTerm, setSearchTerm] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [deleteWorkflowId, setDeleteWorkflowId] = useState<string | null>(null);
  const { workflows, addWorkflow, deleteWorkflow } = useAppContext();

  const filteredWorkflows = useMemo(() => {
    if (!searchTerm) return workflows;
    return workflows.filter(
      (workflow) =>
        workflow.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        workflow.description.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [searchTerm, workflows]);

  const workflowsByCategory = useMemo(() => {
    type Category = 'today' | 'yesterday' | 'last-week' | 'older';
    const result: Record<Category, typeof workflows> = {
      today: [],
      yesterday: [],
      'last-week': [],
      older: [],
    };

    filteredWorkflows.forEach((workflow) => {
      const category = workflowService.getWorkflowCategory(
        workflow.name
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

    const newWorkflow = {
      ...random,
      id: `new-workflow-${Date.now()}`,
      name: getUniqueWorkflowName(
        `${random?.name}`,
        workflows.map((wf) => wf.name)
      ),
      category: 'today',
      lastRun: new Date().toISOString(),
    };

    addWorkflow(newWorkflow);
    console.log('Workflow recording completed!');
    setIsRecording(false);
  };

  const handleDeleteWorkflow = (workflowId: string) => {
    setDeleteWorkflowId(workflowId);
  };

  const confirmDeleteWorkflow = (workflowId: string) => {
    console.log('Deleting workflow:', workflowId);
    deleteWorkflow(deleteWorkflowId);
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

        <SidebarContent className="overflow-y-auto">
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu className="space-y-1">
                {/* {workflowsByCategory.today.length > 0 && (
                  <>
                    <div className="flex items-center justify-center px-4 py-3">
                      <div className="flex items-center w-full">
                        <Separator className="flex-1" />
                        <span className="px-3 text-xs font-medium text-gray-500 bg-white">
                          Today
                        </span>
                        <Separator className="flex-1" />
                      </div>
                    </div>
                    {workflowsByCategory.today.map((workflow) => (
                      <WorkflowItem
                        key={workflow.name}
                        workflow={workflow}
                        onDeleteWorkflow={handleDeleteWorkflow}
                      />
                    ))}
                  </>
                )}

                {workflowsByCategory.yesterday.length > 0 && (
                  <>
                    <div className="flex items-center justify-center px-4 py-3">
                      <div className="flex items-center w-full">
                        <Separator className="flex-1" />
                        <span className="px-3 text-xs font-medium text-gray-500 bg-white">
                          Yesterday
                        </span>
                        <Separator className="flex-1" />
                      </div>
                    </div>
                    {workflowsByCategory.yesterday.map((workflow) => (
                      <WorkflowItem
                        key={workflow.name}
                        workflow={workflow}
                        onDeleteWorkflow={handleDeleteWorkflow}
                      />
                    ))}
                  </>
                )}

                {workflowsByCategory['last-week'].length > 0 && (
                  <>
                    <div className="flex items-center justify-center px-4 py-3">
                      <div className="flex items-center w-full">
                        <Separator className="flex-1" />
                        <span className="px-3 text-xs font-medium text-gray-500 bg-white">
                          Last Week
                        </span>
                        <Separator className="flex-1" />
                      </div>
                    </div>
                    {workflowsByCategory['last-week'].map((workflow) => (
                      <WorkflowItem
                        key={workflow.name}
                        workflow={workflow}
                        onDeleteWorkflow={handleDeleteWorkflow}
                      />
                    ))}
                  </>
                )}

                {workflowsByCategory.older.length > 0 && (
                  <>
                    <div className="flex items-center justify-center px-4 py-3">
                      <div className="flex items-center w-full">
                        <Separator className="flex-1" />
                        <span className="px-3 text-xs font-medium text-gray-500 bg-white">
                          Older
                        </span>
                        <Separator className="flex-1" />
                      </div>
                    </div>
                    {workflowsByCategory.older.map((workflow) => (
                      <WorkflowItem
                        key={workflow.name}
                        workflow={workflow}
                        onDeleteWorkflow={handleDeleteWorkflow}
                      />
                    ))}
                  </>
                )} */}
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
                  label="Older"
                  workflows={workflowsByCategory.older}
                  onDeleteWorkflow={handleDeleteWorkflow}
                />

                {filteredWorkflows.length === 0 && (
                  <div className="p-4 text-center text-gray-500">
                    No workflows found matching "{searchTerm}"
                  </div>
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
