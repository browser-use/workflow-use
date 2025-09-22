import { WorkflowMetadata, Workflow } from '../types/workflow-layout.types';

export function extractMetadata(workflow: Workflow): WorkflowMetadata {
  const metadata: WorkflowMetadata = {
    name: workflow.name,
    description: workflow.description,
    version: workflow.version,
    input_schema: workflow.input_schema,
    workflow_analysis: workflow.workflow_analysis
  };
  
  return metadata;
}
