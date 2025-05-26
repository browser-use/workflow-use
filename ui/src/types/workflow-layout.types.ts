import { z } from 'zod';
import type { Node, BuiltInNode } from '@xyflow/react';

export type PositionLoggerNode = Node<{ label: string }, 'position-logger'>;
export type AppNode = BuiltInNode | PositionLoggerNode;

/* ── Input field definition ────────────────────────────────────────── */
export const inputFieldSchema = z.object({
  name: z.string(),
  type: z.enum(['string', 'number', 'boolean']),
  required: z.boolean(),
  value: z.any(),
});

/* ── Step definition ───────────────────────────────────────────────── */
export const stepSchema = z.object({
  /* core fields */
  description: z.string(),
  output: z.unknown().nullable(),
  timestamp: z.number().int().nullable(),
  tabId: z.number().int().nullable(),
  type: z.enum([
    'navigation',
    'click',
    'select_change',
    'input',
    'agent',
    'key_press',
  ]),

  /* optional fields (vary by step type) */
  url: z.string().url().nullable().optional(),
  cssSelector: z.string().nullable().optional(),
  xpath: z.string().nullable().optional(),
  elementTag: z.string().nullable().optional(),
  elementText: z.string().nullable().optional(),
  selectedText: z.string().nullable().optional(),
  value: z.string().nullable().optional(),
  task: z.string().nullable().optional(),
});

/* ── Workflow wrapper ──────────────────────────────────────────────── */
export const workflowSchema = z.object({
  workflow_analysis: z.string(),
  name: z.string(),
  description: z.string(),
  version: z.string(),
  steps: z.array(stepSchema),
  input_schema: z.array(inputFieldSchema),
});

/* ── Inferred TypeScript type ───────────────────────────────────────– */
export type Workflow = z.infer<typeof workflowSchema>;

export interface WorkflowStep {
  description: string;
  type: string;
  [key: string]: any;
}

export interface WorkflowMetadata {
  name: string;
  description: string;
  version: string;
  input_schema: any[];
  workflow_analysis?: string;
}
