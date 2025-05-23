import { Workflow } from './workflow-layout.types';

export interface SidebarProps {
  onSelect: (workflowName: string) => void;
  selected: string | null;
  workflowsData: Record<string, Workflow>;
  onUpdateWorkflow: (workflowName: string, workflow: Workflow) => Promise<void>;
}