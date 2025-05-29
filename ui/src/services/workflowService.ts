import { fetchClient } from '../lib/api';
import {
  Workflow,
  WorkflowMetadata,
  inputFieldSchema,
} from '../types/workflow-layout.types';
import { z } from 'zod';

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
  recordWorkflow(): Promise<any>;
  stopRecording(): Promise<any>;
  fetchWorkflowLogs(taskId: string, position: number): Promise<any>;
  cancelWorkflow(taskId: string): Promise<any>;
  deleteStep(
    workflowName: string,
    stepIndex: number
  ): Promise<{ success: boolean; error?: string }>;
}

class WorkflowServiceImpl implements WorkflowService {
  async getWorkflows(): Promise<Workflow[]> {
    const response = await fetchClient.GET('/api/workflows');

    const workflowNames = response.data?.workflows ?? [];

    // Fetch full workflow data for each workflow name
    const workflows = await Promise.all(
      workflowNames.map((name) => this.getWorkflowByName(name))
    );

    return workflows;
  }

  async getWorkflowByName(name: string): Promise<any> {
    const response = await fetchClient.GET('/api/workflows/{name}', {
      params: { path: { name } },
    });
    if (!response.data) {
      throw new Error('Failed to return data from server');
    }
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
    if (!response.data) {
      throw new Error('Failed to return data from server');
    }
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
    if (!response.data) {
      throw new Error('Failed to return data from server');
    }
    return response.data;
  }

  async deleteStep(workflowName: string, stepIndex: number): Promise<any> {
    const response = await fetchClient.POST('/api/workflows/delete-step', {
      body: { workflowName, stepIndex },
    });
    console.log('Response from deleteStep:', response);
    if (!response.data) {
      throw new Error('Failed to return data from server');
    }
    return response.data;
  }

  async executeWorkflow(
    name: string,
    inputFields: z.infer<typeof inputFieldSchema>[]
  ): Promise<{
    task_id: string;
    log_position: number;
    message: string;
  }> {
    const inputs: any = {};
    inputFields.forEach((field) => {
      inputs[field.name] = field.value;
    });

    const response = await fetchClient.POST('/api/workflows/execute', {
      body: { name, inputs },
    });
    if (!response.data) {
      throw new Error('Failed to return data from server');
    }

    return response.data;
  }

  async recordWorkflow(): Promise<any> {
    const response = await fetchClient.POST('/api/workflows/record', {
      body: undefined,
    });
    if (!response.data) {
      throw new Error('Failed to return data from server');
    }
    return response.data;
  }

  async stopRecording(): Promise<any> {
    const response = await fetchClient.POST('/api/workflows/cancel-recording', {
      body: undefined,
    });
    if (!response.data) {
      throw new Error('Failed to return data from server');
    }
    return response.data;
  }

  async buildWorkflow(
    name: string,
    prompt: string,
    workflow: any
  ): Promise<any> {
    const response = await fetchClient.POST(
      '/api/workflows/build-from-recording',
      {
        body: { name, prompt, workflow },
      }
    );
    if (!response.data) {
      throw new Error('Failed to return data from server');
    }
    return response.data;
  }

  async addWorkflow(name: string, content: string): Promise<void> {
    const response = await fetchClient.POST('/api/workflows/add', {
      body: { name, content },
    });

    if (!response.data) {
      throw new Error('Failed to add workflow');
    }

    const data = response.data;
    if (!data.success) {
      throw new Error(data.error || 'Failed to add workflow');
    }
  }

  async deleteWorkflow(name: string): Promise<void> {
    const response = await fetchClient.DELETE('/api/workflows/{name}', {
      params: { path: { name } },
    });

    if (!response.data) {
      throw new Error('Failed to delete workflow');
    }

    const data = response.data;
    if (!data.success) {
      throw new Error(data.error || 'Failed to delete workflow');
    }
  }

  async fetchWorkflowLogs(taskId: string, position: number) {
    const response = await fetchClient.GET('/api/workflows/logs/{task_id}', {
      params: { path: { task_id: taskId }, query: { position } },
    });

    if (!response.data) {
      throw new Error('Failed to return data from server');
    }

    return response.data;
  }

  async cancelWorkflow(taskId: string) {
    const response = await fetchClient.POST(
      '/api/workflows/tasks/{task_id}/cancel',
      {
        params: { path: { task_id: taskId } },
      }
    );

    if (!response.data) {
      throw new Error('Failed to return data from server');
    }

    const data = response.data;
    if (!data?.success) {
      throw new Error(data.message || 'Failed to cancel workflow');
    }

    return data;
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
