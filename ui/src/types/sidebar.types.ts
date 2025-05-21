import { type WorkflowMetadata } from './workflow-layout.types';

export interface SidebarProps {
  workflows: string[];
  onSelect: (wf: string) => void;
  selected: string | null;
  workflowMetadata: WorkflowMetadata | null;
  onUpdateMetadata: (metadata: WorkflowMetadata) => Promise<void>;
  allWorkflowsMetadata?: Record<string, WorkflowMetadata>;
}