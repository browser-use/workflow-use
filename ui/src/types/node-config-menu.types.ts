import type { Node } from '@xyflow/react';

export interface StepData {
  description: string;
  output?: unknown;
  timestamp: number | null;
  tabId: number | null;
  type: 'navigation' | 'click' | 'select_change' | 'input';
  url?: string;
  cssSelector?: string;
  xpath?: string;
  elementTag?: string;
  elementText?: string;
  selectedText?: string;
  value?: string;
}

export interface NodeData extends Record<string, unknown> {
  label: string;
  stepData: StepData;
  workflowName?: string;
}

export interface NodeConfigMenuProps {
    node: Node<NodeData> | null;
    onClose: () => void;
    workflowFilename: string | null;
}