// components/WorkflowCategoryBlock.tsx
import React from 'react';
import { Separator } from '@/components/ui/separator';
import { WorkflowItem } from '@/components/WorkflowItem';
import { Workflow } from '@/types/workflow-layout.types';

interface Props {
  label: string;
  workflows: Workflow[];
  onDeleteWorkflow: (workflowId: string) => void;
}

export const WorkflowCategoryBlock: React.FC<Props> = ({
  label,
  workflows,
  onDeleteWorkflow,
}) => {
  if (!workflows || workflows.length === 0) return null;

  return (
    <>
      <div className="flex items-center justify-center px-4 py-3">
        <div className="flex items-center w-full">
          <Separator className="flex-1" />
          <span className="px-3 text-xs font-medium text-gray-500 bg-white">
            {label}
          </span>
          <Separator className="flex-1" />
        </div>
      </div>
      {workflows.map((workflow) => (
        <WorkflowItem
          key={`${workflow.name}-${workflow.version}`}
          workflow={workflow}
          onDeleteWorkflow={onDeleteWorkflow}
        />
      ))}
    </>
  );
};
