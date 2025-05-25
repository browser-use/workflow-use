import { fetchClient } from '../lib/api';
import { Workflow, WorkflowMetadata } from '../types/workflow-layout.types';
import { InputField } from '../types/play-button.types';

// Local file simulating persistent storage
import runtimeJson from '@/data/runtimes/workflow-runtimes.json';

export interface WorkflowService {
  getWorkflows(): Promise<Workflow[]>;
  getWorkflowByName(name: string): Promise<any>;
  updateWorkflowMetadata(
    name: string,
    metadata: WorkflowMetadata
  ): Promise<void>;
  executeWorkflow(
    name: string,
    inputFields: InputField[]
  ): Promise<{
    taskId: string;
    logPosition: number;
  }>;
  updateWorkflowRuntime(name: string, timestamp: Date): void;
  getWorkflowCategory(name: string): string;
  updateWorkflow(
    filename: string,
    nodeId: number,
    stepData: any
  ): Promise<void>;
}

class WorkflowServiceImpl implements WorkflowService {
  async getWorkflows(): Promise<Workflow[]> {
    console.log('Fetching list of workflows...');
    const response = await fetchClient.GET('/api/workflows');
    console.log('Received response for workflows:', response.data);

    const workflowNames = response.data?.workflows ?? [];
    console.log('Workflow names extracted:', workflowNames);

    // Fetch full workflow data for each workflow name
    const workflows = await Promise.all(
      workflowNames.map((name) => this.getWorkflowByName(name))
    );

    console.log('Fetched full workflow data:', workflows);
    return workflows;
  }

  async getWorkflowByName(name: string): Promise<any> {
    const response = await fetchClient.GET('/api/workflows/{name}', {
      params: { path: { name } },
    });
    return response.data;
  }

  async updateWorkflowMetadata(
    name: string,
    metadata: WorkflowMetadata
  ): Promise<any> {
    const response = await fetchClient.POST('/api/workflows/update-metadata', {
      body: { name, metadata: metadata as any },
    });
    console.log('Response from updateWorkflowMetadata:', response);
    return response.data;
  }

  async updateWorkflow(
    filename: string,
    nodeId: number,
    stepData: any
  ): Promise<any> {
    const response = await fetchClient.POST('/api/workflows/update', {
      body: { filename, nodeId, stepData },
    });
    console.log('Response from updateWorkflow:', response);
    return response.data;
  }

  async executeWorkflow(
    name: string,
    inputFields: InputField[]
  ): Promise<{
    taskId: string;
    logPosition: number;
  }> {
    const inputs: Record<string, any> = {};
    inputFields.forEach((field) => {
      inputs[field.name] = field.value;
    });

    const response = await fetch(
      'http://127.0.0.1:8000/api/workflows/execute',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, inputs }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to execute workflow');
    }

    const data = await response.json();
    // Update runtime immediately after execution
    this.updateWorkflowRuntime(name, new Date());

    return data;
  }

  updateWorkflowRuntime(name: string, timestamp: Date) {
    const runtimes = { ...runtimeJson };
    runtimes[name] = { lastRun: timestamp.toISOString() };

    try {
      // Store in localStorage instead of file system
      localStorage.setItem('workflow-runtimes', JSON.stringify(runtimes));
    } catch (err) {
      console.error('Failed to update workflow runtime', err);
    }
  }

  getWorkflowCategory(name: string): string {
    const runtimeData = runtimeJson[name];
    if (!runtimeData?.lastRun) return 'older';

    const lastRun = new Date(runtimeData.lastRun);
    const now = new Date();

    const diff = now.getTime() - lastRun.getTime();
    const diffInDays = diff / (1000 * 60 * 60 * 24);

    if (diffInDays < 1 && lastRun.getDate() === now.getDate()) return 'today';
    if (diffInDays < 2) return 'yesterday';
    if (diffInDays < 7) return 'last-week';
    return 'older';
  }
}

export const workflowService = new WorkflowServiceImpl();
