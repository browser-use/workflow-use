import React, {
  useState,
  useCallback,
  useLayoutEffect,
  MouseEvent,
  useEffect,
} from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type OnConnect,
  useReactFlow,
  type Node,
  type Edge,
} from "@xyflow/react";
import { NodeData } from "../types/node-config-menu.types";
import { jsonToFlow } from "../utils/json-to-flow";
import { type WorkflowMetadata } from "../types/workflow-layout.types";
import Sidebar from "./sidebar";
import { NodeConfigMenu } from "./node-config-menu";
import { PlayButton } from "./play-button";
import NoWorkflowsMessage from "./no-workflow-message";
import { $api } from "../lib/api";

const WorkflowLayout: React.FC = () => {
  const [selected, setSelected] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<NodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNode, setSelectedNode] = useState<Node<NodeData> | null>(null);
  const [workflowMetadata, setWorkflowMetadata] =
    useState<WorkflowMetadata | null>(null);
  const [savedNodePositions, setSavedNodePositions] = useState<
    Record<string, Record<string, { x: number; y: number }>>
  >({});
  const { fitView } = useReactFlow();

  // ----- Queries using $api -----
  // Fetch all workflows
  const { data: workflowsResponse, isLoading: isLoadingWorkflows } =
    $api.useQuery("get", "/api/workflows");

  const workflows: string[] = React.useMemo(
    () => workflowsResponse?.workflows ?? [],
    [workflowsResponse?.workflows]
  );

  // Fetch a specific workflow (enabled only when selected is truthy)
  const { data: selectedWorkflow, isLoading: isLoadingSelectedWorkflow } =
    $api.useQuery(
      "get",
      "/api/workflows/{name}",
      selected
        ? {
            params: { path: { name: selected } },
          }
        : { params: { path: { name: "" } } },
      {
        enabled: !!selected,
      }
    );

  // Mutation for updating workflow metadata
  const updateMetadataMutation = $api.useMutation(
    "post",
    "/api/workflows/update-metadata"
  );

  const updateWorkflowMetadata = useCallback(
    async (name: string, metadata: WorkflowMetadata) => {
      await updateMetadataMutation.mutateAsync({
        body: { name, metadata: metadata as unknown as Record<string, never> },
      });
    },
    [updateMetadataMutation]
  );

  const isUpdating = updateMetadataMutation.isPending;

  const onConnect: OnConnect = useCallback(
    (connection) => setEdges((edges) => addEdge(connection, edges)),
    [setEdges]
  );

  // Handle node click to show configuration
  const onNodeClick = useCallback((_: MouseEvent, node: Node) => {
    setSelectedNode(node as Node<NodeData>);
  }, []);

  // Close the node configuration menu
  const closeNodeMenu = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Fit view when nodes change
  useLayoutEffect(() => {
    if (nodes.length > 0) {
      window.requestAnimationFrame(() => {
        fitView({ padding: 0.2 });
      });
    }
  }, [nodes.length, fitView]);

  // Update nodes and edges when selected workflow changes
  useEffect(() => {
    if (selectedWorkflow) {
      const flowData = jsonToFlow(selectedWorkflow);

      // Apply saved positions if available
      if (selected && savedNodePositions[selected]) {
        const savedPositionsForWorkflow = savedNodePositions[selected] || {};
        const nodesWithSavedPositions = flowData.nodes.map((node: Node<NodeData>) => {
          const savedPosition = savedPositionsForWorkflow[node.id];
          if (savedPosition) {
            return {
              ...node,
              position: savedPosition,
            };
          }
          return node;
        });
        setNodes(nodesWithSavedPositions);
      } else {
        setNodes(flowData.nodes);
      }

      setEdges(flowData.edges);
      setWorkflowMetadata(flowData.metadata);
    }
  }, [selectedWorkflow, selected, savedNodePositions, setNodes, setEdges]);

  // Handle node drag stop to save positions
  const onNodeDragStop = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (selected) {
        setSavedNodePositions((prev) => {
          const workflowPositions = prev[selected] || {};
          return {
            ...prev,
            [selected]: {
              ...workflowPositions,
              [node.id]: { x: node.position.x, y: node.position.y },
            },
          };
        });
      }
    },
    [selected]
  );

  // Auto-select first workflow if none selected
  useEffect(() => {
    if (workflows.length > 0 && !selected) {
      setSelected(workflows[0]!);
    }
  }, [workflows, selected]);

  const isLoading = isLoadingWorkflows || isLoadingSelectedWorkflow;

  if (isLoading) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-[#2a2a2a] text-white">
        <img
          src="/browseruse.png"
          alt="Loading..."
          className="mb-5 h-auto w-30 animate-spin"
        />
        <div className="text-lg">Loading workflows...</div>
      </div>
    );
  }

  if (!workflows.length) return <NoWorkflowsMessage />;

  return (
    <div className="flex h-screen font-sans">
      <Sidebar
        workflows={workflows}
        onSelect={setSelected}
        selected={selected}
        workflowMetadata={workflowMetadata}
        onUpdateMetadata={async (metadata: WorkflowMetadata) => {
          if (selected) {
            await updateWorkflowMetadata(selected, metadata);
          }
        }}
      />

      <div className="relative flex-1">
        {nodes.length ? (
          <>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              colorMode="dark"
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              onNodeDragStop={onNodeDragStop}
              fitView
            >
              <Background />
              <MiniMap />
              <Controls />
            </ReactFlow>

            {/* actions */}
            <div className="absolute right-5 top-5 z-10 flex gap-2">
              <PlayButton
                workflowName={selected}
                workflowMetadata={workflowMetadata}
              />

              <button
                title="Refresh workflow"
                className="flex h-9 w-9 items-center justify-center rounded-full bg-[#2a2a2a] text-white shadow transition-transform duration-200 ease-in-out hover:scale-105 hover:bg-blue-500"
                onClick={async () => {
                  if (selected && workflowMetadata) {
                    await updateWorkflowMetadata(selected, workflowMetadata);
                  }
                }}
                disabled={isUpdating}
              >
                {/* hero‑icons refresh */}
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3" />
                </svg>
              </button>
            </div>
          </>
        ) : (
          <div className="m-8 text-gray-500">
            Select a workflow to visualize
          </div>
        )}

        {selectedNode && (
          <NodeConfigMenu
            node={selectedNode}
            onClose={closeNodeMenu}
            workflowFilename={selected}
          />
        )}
      </div>
    </div>
  );
};

export default WorkflowLayout;
