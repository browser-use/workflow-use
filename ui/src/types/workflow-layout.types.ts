import { z } from 'zod';
import type { Node, BuiltInNode } from '@xyflow/react';

export type PositionLoggerNode = Node<{ label: string }, 'position-logger'>;
export type AppNode = BuiltInNode | PositionLoggerNode;

/* ── Input field definition ────────────────────────────────────────── */
const inputFieldSchema = z.object({
  name: z.string(),
  type: z.enum(['string', 'number', 'boolean']),
  required: z.boolean(),
});

/* ── Step definition ───────────────────────────────────────────────── */
const stepSchema = z.object({
  /* core fields */
  description: z.string(),
  output: z.unknown().nullable(),
  timestamp: z.number().int().nullable(),
  tabId: z.number().int().nullable(),
  type: z.enum(['navigation', 'click', 'select_change', 'input']),

  /* optional fields (vary by step type) */
  url: z.string().url().optional(),
  cssSelector: z.string().optional(),
  xpath: z.string().optional(),
  elementTag: z.string().optional(),
  elementText: z.string().optional(),
  selectedText: z.string().optional(),
  value: z.string().optional(),
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

/* -- Inferred TypeScript type ---------------------------------------- */
export type Workflow = z.infer<typeof workflowSchema>;

export interface WorkflowStep {
  description: string;
  type: string;
  [key: string]: unknown;
}

export interface WorkflowMetadata {
  name: string;
  description: string;
  version: string;
  input_schema: Array<{ name: string; type: 'string' | 'number' | 'boolean'; required: boolean }>;
  workflow_analysis?: string;
}

export interface WorkflowItemProps {
  id: string;
  selected: boolean;
  metadata?: WorkflowMetadata;
  onSelect: (id: string) => void;
  onUpdateMetadata: (m: WorkflowMetadata) => Promise<void>;
}
