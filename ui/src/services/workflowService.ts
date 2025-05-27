import { fetchClient } from '../lib/api';
import {
  Workflow,
  WorkflowMetadata,
  inputFieldSchema,
} from '../types/workflow-layout.types';
import { z } from 'zod';

interface WorkflowResponse {
  success: boolean;
  error?: string;
}

export interface WorkflowService {
  getWorkflows(): Promise<Workflow[]>;
  getWorkflowByName(name: string): Promise<any>;
  updateWorkflowMetadata(
    name: string,
    metadata: WorkflowMetadata
  ): Promise<void>;
  executeWorkflow(
    name: string,
    inputFields: z.infer<typeof inputFieldSchema>[]
  ): Promise<{
    task_id: string;
    log_position: number;
  }>;
  getWorkflowCategory(timestamp: number): string;
  addWorkflow(name: string, content: string): Promise<void>;
  deleteWorkflow(name: string): Promise<void>;
  buildWorkflow(name: string, prompt: string, workflow: any): Promise<any>;
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
    inputFields: z.infer<typeof inputFieldSchema>[]
  ): Promise<{
    task_id: string;
    log_position: number;
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
    return data;
  }

  async recordWorkflow(): Promise<any> {
    const response = await fetch('http://localhost:8000/api/workflows/record', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    return response.json();
  }

  async buildWorkflow(
    name: string,
    prompt: string,
    workflow: any
  ): Promise<any> {
    const response = await fetch(
      'http://localhost:8000/api/workflows/build-from-recording',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, prompt, workflow }),
      }
    );
    return response.json();
  }

  async addWorkflow(name: string, content: string): Promise<void> {
    const response = await fetch('http://localhost:8000/api/workflows/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, content }),
    });

    if (!response.ok) {
      throw new Error('Failed to add workflow');
    }

    const data = (await response.json()) as WorkflowResponse;
    if (!data.success) {
      throw new Error(data.error || 'Failed to add workflow');
    }
  }

  async deleteWorkflow(name: string): Promise<void> {
    const response = await fetch(
      `http://localhost:8000/api/workflows/${name}`,
      {
        method: 'DELETE',
      }
    );

    if (!response.ok) {
      throw new Error('Failed to delete workflow');
    }

    const data = (await response.json()) as WorkflowResponse;
    if (!data.success) {
      throw new Error(data.error || 'Failed to delete workflow');
    }
  }

  getWorkflowCategory(timestamp: number): string {
    const now = new Date();
    const lastRun = new Date(timestamp);

    const diff = now.getTime() - lastRun.getTime();
    const diffInDays = diff / (1000 * 60 * 60 * 24);

    if (diffInDays < 1 && lastRun.getDate() === now.getDate()) return 'today';
    if (diffInDays < 2) return 'yesterday';
    if (diffInDays < 7) return 'last-week';
    if (diffInDays < 30) return 'last-month';
    return 'older';
  }
}

export const workflowService = new WorkflowServiceImpl();
