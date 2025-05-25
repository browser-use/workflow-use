import React, { useCallback, useMemo, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
  MarkerType,
  ReactFlowInstance,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { WorkflowStepNode } from './WorkflowStepNode';
import { useAppContext } from '@/contexts/AppContext';

const nodeTypes = {
  workflowStep: WorkflowStepNode,
};

export function WorkflowCanvas() {
  const { currentWorkflowData } = useAppContext();
  const reactFlowInstanceRef = useRef<ReactFlowInstance | null>(null);

  const initialNodes: Node[] = useMemo(() => {
    if (!currentWorkflowData) {
      return [
        {
          id: 'placeholder',
          type: 'workflowStep',
          position: { x: 250, y: 200 },
          data: {
            label: 'Select a workflow to visualize',
            action: 'info',
            target: '',
            stepNumber: 1,
          },
        },
      ];
    }

    return currentWorkflowData.steps.map((step, index) => ({
      id: `step-${index + 1}`,
      type: 'workflowStep',
      position: { x: 100, y: 100 + index * 150 },
      data: {
        description: step.description,
        action: step.type,
        target: step.cssSelector,
        value: step.value,
        stepNumber: index + 1,
      },
    }));
  }, [currentWorkflowData]);

  const initialEdges: Edge[] = useMemo(() => {
    if (!currentWorkflowData) return [];

    return currentWorkflowData.steps.slice(0, -1).map((_, index) => ({
      id: `e-step-${index + 1}-step-${index + 2}`,
      source: `step-${index + 1}`,
      target: `step-${index + 2}`,
      type: 'smoothstep',
      markerEnd: { type: MarkerType.ArrowClosed },
    }));
  }, [currentWorkflowData]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  // Update nodes when currentWorkflowData changes
  React.useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
    requestAnimationFrame(() => {
      reactFlowInstanceRef.current?.fitView({ padding: 0.2 });
    });
  }, [currentWorkflowData, initialNodes, initialEdges, setNodes, setEdges]);

  return (
    <div className="w-full h-full bg-gray-50">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        onInit={(instance) => {
          reactFlowInstanceRef.current = instance;
        }}
        fitView
        style={{ backgroundColor: '#f9fafb' }}
        defaultViewport={{ x: 0, y: 0, zoom: 0 }}
      >
        <Background color="#e5e7eb" gap={20} />
        <Controls className="bg-white border border-gray-200 rounded-lg shadow-sm" />
        <MiniMap
          className="bg-white border border-gray-200 rounded-lg shadow-sm"
          nodeColor={(node) => {
            if (node.data?.action === 'navigation') return '#3b82f6';
            if (node.data?.action === 'click') return '#10b981';
            if (node.data?.action === 'input') return '#f59e0b';
            if (node.data?.action === 'key_press') return '#8b5cf6';
            if (node.data?.action === 'agent') return '#6b7280';
            if (node.data?.action === 'select_change') return '#06b6d4';
            return '#6b7280';
          }}
        />
      </ReactFlow>
    </div>
  );
}
