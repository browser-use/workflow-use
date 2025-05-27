import { Workflow as WorkflowIcon, Trash2 } from 'lucide-react';
import { SidebarMenuItem, SidebarMenuButton } from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Workflow } from '../types/workflow-layout.types';
import { useAppContext } from '@/contexts/AppContext';

interface WorkflowItemProps {
  workflow: Workflow;
  onDeleteWorkflow: (workflowId: string) => void;
}

export function WorkflowItem({
  workflow,
  onDeleteWorkflow,
}: WorkflowItemProps) {
  const { currentWorkflowData, selectWorkflow, displayMode, setDisplayMode } =
    useAppContext();

  const handleClick = () => {
    selectWorkflow(workflow.name);
    if (displayMode === 'start') {
      setDisplayMode('canvas');
    }
  };

  return (
    <SidebarMenuItem key={workflow.name}>
      <SidebarMenuButton
        onClick={handleClick}
        className={cn(
          'w-full p-4 text-left hover:bg-gray-100 transition-colors rounded-md min-h-[80px] relative group',
          currentWorkflowData?.name === workflow.name &&
            'bg-purple-50 border-r-2 border-purple-500'
        )}
      >
        <div className="flex items-start gap-3 w-full pr-8">
          <div className="flex items-center justify-center w-8 h-8 bg-gray-100 rounded-md mt-0.5 flex-shrink-0">
            <WorkflowIcon className="w-4 h-4 text-gray-600" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-gray-900 text-sm leading-tight mb-1">
              {workflow.name}
            </h3>
            <p className="text-xs text-gray-500 leading-tight mb-2 truncate whitespace-nowrap overflow-hidden">
              {workflow.description}
            </p>
            <span className="text-xs text-purple-600 font-medium">
              {workflow.steps?.length ?? 0} steps
            </span>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            onDeleteWorkflow(workflow.name);
          }}
          className="absolute top-1/2 right-3 transform -translate-y-1/2 p-1.5 w-7 h-7 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-100 hover:text-red-600"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}
