import { Workflow } from './workflow-layout.types';

export interface PlayButtonProps {
  workflowName: string | null;
  workflowData: Workflow | null;
}

export interface InputField {
  name: string;
  type: string;
  required: boolean;
  value: any;
}