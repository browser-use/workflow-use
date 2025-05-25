import React, { useCallback, useMemo } from 'react';
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
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { WorkflowStepNode } from './WorkflowStepNode';
import { useAppContext } from '@/contexts/AppContext';

const nodeTypes = {
  workflowStep: WorkflowStepNode,
};

export function WorkflowCanvas() {
  const { currentWorkflowData, selectedWorkflow } = useAppContext();

  const initialNodes: Node[] = useMemo(() => {
    if (!currentWorkflowData || !selectedWorkflow) {
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
      id: `step-${index}`,
      type: 'workflowStep',
      position: { x: 100, y: 100 + index * 200 },
      data: {
        label: step.description,
        action: step.type,
        target: step.cssSelector,
        value: step.value,
        stepNumber: index,
      },
    }));
  }, [currentWorkflowData, selectedWorkflow]);

  const initialEdges: Edge[] = useMemo(() => {
    if (!currentWorkflowData || !selectedWorkflow) return [];

    return currentWorkflowData.steps.slice(0, -1).map((_, index) => ({
      id: `e-step-${index}-step-${index + 1}`,
      source: `step-${index}`,
      target: `step-${index + 1}`,
      type: 'smoothstep',
      markerEnd: { type: MarkerType.ArrowClosed },
    }));
  }, [currentWorkflowData, selectedWorkflow]);

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
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  return (
    <div className="w-full h-full bg-gray-50">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        style={{ backgroundColor: '#f9fafb' }}
        defaultViewport={{ x: 0, y: 0, zoom: 1 }}
      >
        <Background color="#e5e7eb" gap={20} />
        <Controls className="bg-white border border-gray-200 rounded-lg shadow-sm" />
        <MiniMap
          className="bg-white border border-gray-200 rounded-lg shadow-sm"
          nodeColor={(node) => {
            if (node.data?.action === 'navigate') return '#3b82f6';
            if (node.data?.action === 'click') return '#10b981';
            if (node.data?.action === 'type') return '#f59e0b';
            if (node.data?.action === 'wait') return '#8b5cf6';
            return '#6b7280';
          }}
        />
      </ReactFlow>
    </div>
  );
}
