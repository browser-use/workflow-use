import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import {
  MousePointer,
  Type,
  Navigation,
  Clock,
  Info,
  FileSearch,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface WorkflowStepNodeData {
  description: string;
  action:
    | 'navigation'
    | 'click'
    | 'select_change'
    | 'input'
    | 'agent'
    | 'key_press';
  target: string;
  value?: string;
  stepNumber: number;
}

interface WorkflowStepNodeProps {
  data: WorkflowStepNodeData;
  selected?: boolean;
}

const actionIcons = {
  click: MousePointer,
  input: Type,
  navigation: Navigation,
  key_press: Clock,
  agent: Info,
  select_change: FileSearch,
};

const actionColors = {
  click: 'bg-green-500',
  input: 'bg-amber-500',
  navigation: 'bg-blue-500',
  key_press: 'bg-purple-500',
  agent: 'bg-gray-500',
  select_change: 'bg-cyan-500',
};

export const WorkflowStepNode = memo(
  ({ data, selected }: WorkflowStepNodeProps) => {
    const Icon = actionIcons[data.action] || Info; // Fallback to Info icon if action not found
    const colorClass = actionColors[data.action] || 'bg-gray-500'; // Fallback to gray if color not found

    return (
      <div
        className={cn(
          'bg-white rounded-lg border-2 shadow-sm p-4 w-[380px] h-[100px] transition-all',
          selected ? 'border-purple-500 shadow-md' : 'border-gray-200',
          'hover:shadow-md'
        )}
      >
        {data.stepNumber > 0 && (
          <Handle
            type="target"
            position={Position.Top}
            className="w-3 h-3 bg-gray-400 border-2 border-white"
          />
        )}

        <div className="flex items-start gap-3">
          <div className={cn('p-3 rounded-lg text-white shrink-0', colorClass)}>
            <Icon className="w-8 h-8" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              {data.stepNumber > 0 && (
                <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                  Step {data.stepNumber}
                </span>
              )}
              <span className="text-xs font-medium text-gray-500 bg-purple-100 text-purple-700 px-2 py-1 rounded-full capitalize">
                {data.action}
              </span>
            </div>

            <h3 className="font-medium text-gray-900 text-sm mb-2 break-words line-clamp-2">
              {data.description}
            </h3>
          </div>
        </div>

        {data.stepNumber >= 0 && (
          <Handle
            type="source"
            position={Position.Bottom}
            className="w-3 h-3 bg-gray-400 border-2 border-white"
          />
        )}
      </div>
    );
  }
);

WorkflowStepNode.displayName = 'WorkflowStepNode';
