import { WorkflowMetadata } from './workflow-layout.types';

export interface PlayButtonProps {
  workflowName: string | null;
  workflowMetadata: WorkflowMetadata | null;
}

export interface InputField {
  name: string;
  type: string;
  required: boolean;
  value: string | number | boolean;
}