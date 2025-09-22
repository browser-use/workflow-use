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
} from "@xyflow/react";
import { type Node } from "@xyflow/react";
import { NodeData } from "../types/node-config-menu.types";
import { jsonToFlow } from "../utils/json-to-flow";
import { extractMetadata } from "../utils/extract-metadata";
import { type Workflow } from "../types/workflow-layout.types";
import Sidebar from "./sidebar";
import { NodeConfigMenu } from "./node-config-menu";
import { PlayButton } from "./play-button";
import NoWorkflowsMessage from "./no-workflow-message";
import { $api } from "../lib/api";

const WorkflowLayout: React.FC = () => {
  const [selected, setSelected] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node<NodeData> | null>(null);
  const [workflowsData, setWorkflowsData] = useState<Record<string, Workflow>>({});
  const [isLoadingAllWorkflows, setIsLoadingAllWorkflows] = useState(false);
  const [savedNodePositions, setSavedNodePositions] = useState<
    Record<string, Record<string, { x: number; y: number }>>
  >({});
  const { fitView } = useReactFlow();

  // Get the selected workflow data from our complete data
  const selectedWorkflow = selected ? workflowsData[selected] : null;
  
  // Mutation for updating workflow metadata
  const updateMetadataMutation = $api.useMutation(
    "post",
    "/api/workflows/update-metadata"
  );
  // Mutation for fetching list of workflows
  const workflowListMutation = $api.useMutation(
    "get",
    "/api/workflows"
  );
  // Mutation for fetching individual workflow data
  const workflowFetchMutation = $api.useMutation(
    "get",
    "/api/workflows/{name}"
  );

  const updateWorkflowMetadata = useCallback(
    async (workflowName: string, updatedWorkflow: Workflow) => {
      // Extract metadata for the API call
      const metadata = extractMetadata(updatedWorkflow);
      
      // Update the metadata via API
      await updateMetadataMutation.mutateAsync({
        body: { name: workflowName, metadata } as any,
      });
      
      // Refresh the workflow data
      await refreshWorkflow(workflowName);
    },
    [updateMetadataMutation]
  );
  
  // Function to refresh a workflow - fetches latest data and updates metadata if needed
  const refreshWorkflow = useCallback(
    async (workflowName: string) => {
      // Validate that we have a workflow name and it exists in our data
      if (!workflowName || !workflowsData[workflowName]) return null;
      
      try {
        // Fetch the latest workflow data
        const result = await workflowFetchMutation.mutateAsync({
          params: { path: { name: workflowName } }
        });
        
        if (result) {
          const parsedWorkflow = JSON.parse(result) as Workflow;
          
          setWorkflowsData(prev => ({
            ...prev,
            [workflowName]: parsedWorkflow
          }));
          
          return parsedWorkflow;
        }
      } catch (error) {
        console.error(`Error refreshing workflow ${workflowName}:`, error);
      }
      
      return null;
    },
    [workflowFetchMutation]
  );

  const isUpdating = updateMetadataMutation.isPending;

  const onConnect: OnConnect = useCallback(
    (connection) => setEdges((edges) => addEdge(connection, edges)),
    [setEdges]
  );

  // Handle node click to show configuration
  const onNodeClick = useCallback((_: MouseEvent, node: Node<NodeData>) => {
    setSelectedNode(node);
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
        const nodesWithSavedPositions = flowData.nodes.map((node: any) => {
          const savedPosition = savedPositionsForWorkflow[node.id];
          if (savedPosition) {
            return {
              ...node,
              position: savedPosition,
            };
          }
          return node;
        });
        setNodes(nodesWithSavedPositions as any);
      } else {
        setNodes(flowData.nodes as any);
      }

      setEdges(flowData.edges as any);
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
  
  // Load all workflow data on component mount
  useEffect(() => {
    // Function to fetch all workflow data at once
    const fetchAllWorkflowsData = async () => {
      setIsLoadingAllWorkflows(true);
      
      const processedData: Record<string, any> = {};
      
      try {
        const workflowsListResponse = await workflowListMutation.mutateAsync({});
        const workflowNames = workflowsListResponse?.workflows ?? [];
        
        for (const workflowName of workflowNames) {
          try {
            const result = await workflowFetchMutation.mutateAsync({
              params: { path: { name: workflowName } }
            });
            
            if (result) {
              // Parse the JSON string into a Workflow object
              const parsedWorkflow: Workflow = JSON.parse(result);
              processedData[workflowName] = parsedWorkflow;
            }
          } catch (error) {
            console.error(`Error fetching data for ${workflowName}:`, error);
          }
        }
        
        // Update state with all workflow data
        setWorkflowsData(processedData);
      } catch (error) {
        console.error('Error fetching all workflow data:', error);
      } finally {
        setIsLoadingAllWorkflows(false);
      }
    };
    
    fetchAllWorkflowsData();
  }, []);

   // Auto-select first workflow if none selected
  useEffect(() => {
    const workflowKeys = Object.keys(workflowsData);
    if (workflowKeys.length > 0 && !selected) {
      setSelected(workflowKeys[0] || null);
    }
  }, [workflowsData, selected]);

  if (isLoadingAllWorkflows) {
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

  if (!Object.keys(workflowsData).length) return <NoWorkflowsMessage />;

  return (
    <div className="flex h-screen font-sans">
      <Sidebar
        onSelect={setSelected}
        selected={selected}
        workflowsData={workflowsData}
        onUpdateWorkflow={updateWorkflowMetadata}
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
                workflowData={selected && workflowsData[selected] ? workflowsData[selected] : null}
              />

              <button
                title="Refresh workflow"
                className="flex h-9 w-9 items-center justify-center rounded-full bg-[#2a2a2a] text-white shadow transition-transform duration-200 ease-in-out hover:scale-105 hover:bg-blue-500"
                onClick={() => selected && refreshWorkflow(selected)}
                disabled={isUpdating}
              >
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
