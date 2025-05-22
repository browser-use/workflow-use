import { Edge } from '@xyflow/react';
import { Workflow, WorkflowStep, AppNode } from '../types/workflow-layout.types';

export function jsonToFlow(workflow: Workflow): { 
  nodes: AppNode[]; 
  edges: Edge[];
} {
  const nodes: AppNode[] = workflow.steps.map((step: WorkflowStep, idx: number) => ({
    id: String(idx),
    data: { 
      label: `${step.description}`, 
      stepData: step,
      workflowName: workflow.name
    },
    position: { x: 0, y: idx * 100 }
  }));

  const edges: Edge[] = workflow.steps.slice(1).map((_, idx) => ({
    id: `e${idx}-${idx + 1}`,
    source: String(idx),
    target: String(idx + 1),
    animated: true,
  }));

  return { nodes, edges };
}