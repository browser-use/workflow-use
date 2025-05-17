import React, { useState, useEffect, useCallback, useLayoutEffect, MouseEvent } from 'react';
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
} from '@xyflow/react';
import {type Node } from '@xyflow/react';
import { NodeData } from '../types/node-config-menu.types';
import { jsonToFlow } from '../utils/json-to-flow';
import { type WorkflowMetadata } from '../types/workflow-layout.types';
import { Sidebar } from './sidebar';
import { NodeConfigMenu } from './node-config-menu';
import { PlayButton } from './play-button';
import NoWorkflowsMessage from './no-workflow-message';

const WorkflowLayout: React.FC = () => {
  const [workflows, setWorkflows] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node<NodeData> | null>(null);
  const [workflowMetadata, setWorkflowMetadata] = useState<WorkflowMetadata | null>(null);
  const [allWorkflowsMetadata, setAllWorkflowsMetadata] = useState<Record<string, WorkflowMetadata>>({});
  const [isLoading, setIsLoading] = useState(true);
  // Store node positions for each workflow
  const [savedNodePositions, setSavedNodePositions] = useState<Record<string, Record<string, { x: number, y: number }>>>({});
  const { fitView } = useReactFlow();

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

  // Function to fetch all workflows
  const fetchWorkflows = useCallback(async () => {
    setIsLoading(true);
    try {
      // Add cache-busting query parameter to prevent caching
      const resp = await fetch(`http://localhost:8000/api/workflows?_=${Date.now()}`);
      if (!resp.ok) {
        throw new Error(`Failed to fetch workflows: ${resp.status} ${resp.statusText}`);
      }
      
      const files = await resp.json();
      setWorkflows(files);
      
      // Auto-select the first workflow if available and none is currently selected
      if (files && files.length > 0 && !selected) {
        setSelected(files[0]);
      }
      
      // Fetch metadata for all workflows - but don't await all of them
      // This prevents one slow request from blocking everything
      files.forEach(async (workflowName: string) => {
        try {
          // Add cache-busting query parameter to prevent caching
          const response = await fetch(`http://localhost:8000/api/workflows/${workflowName}?_=${Date.now()}`);
          if (response.ok) {
            const workflowData = await response.json();
            const flowData = jsonToFlow(workflowData);
            
            // Store metadata in the allWorkflowsMetadata state
            setAllWorkflowsMetadata(prev => ({
              ...prev,
              [workflowName]: flowData.metadata
            }));
          }
        } catch (error) {
          console.error(`Error fetching metadata for ${workflowName}:`, error);
          return null;
        }
      });
    } catch (error) {
      console.error('Error fetching workflows:', error);
    } finally {
      // Always set loading to false, even if there are errors
      setIsLoading(false);
    }
  }, [selected]);
  
  // Function to fetch a specific workflow
  const fetchWorkflow = useCallback(async (workflowName: string) => {
    try {
      // Add cache-busting query parameter to prevent caching
      const resp = await fetch(`http://localhost:8000/api/workflows/${workflowName}?_=${Date.now()}`);
      if (!resp.ok) return;
      
      const wf = await resp.json();
      const flowData = jsonToFlow(wf);
      
      // Apply saved positions if available
      if (savedNodePositions[workflowName]) {
        const nodesWithSavedPositions = flowData.nodes.map((node: any) => {
          const savedPosition = savedNodePositions[workflowName][node.id];
          if (savedPosition) {
            return {
              ...node,
              position: savedPosition
            };
          }
          return node;
        });
        
        setNodes(nodesWithSavedPositions as any);
      } else {
        setNodes(flowData.nodes as any);
      }
      
      setEdges(flowData.edges as any);
      setWorkflowMetadata(flowData.metadata);
    } catch (error) {
      console.error(`Error fetching workflow ${workflowName}:`, error);
    }
  }, [savedNodePositions]);
  
  // Fetch workflows on component mount
  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  // Handle node drag stop to save positions
  const onNodeDragStop = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (selected) {
        // Update the saved positions for just this node
        setSavedNodePositions(prev => {
          const workflowPositions = prev[selected] || {};
          return {
            ...prev,
            [selected]: {
              ...workflowPositions,
              [node.id]: { x: node.position.x, y: node.position.y }
            }
          };
        });
      }
    },
    [selected]
  );
  
  // Load and convert selected workflow
  useEffect(() => {
    if (!selected) return;
    
    async function fetchAndConvert() {
      // Add cache-busting query parameter to prevent caching
      const resp = await fetch(`http://localhost:8000/api/workflows/${selected}?_=${Date.now()}`);
      if (!resp.ok) return;
      
      const wf = await resp.json();
      const flowData = jsonToFlow(wf);
      
      // Apply saved positions if available
      if (selected && savedNodePositions[selected]) {
        const nodesWithSavedPositions = flowData.nodes.map((node: any) => {
          const savedPosition = savedNodePositions[selected][node.id];
          if (savedPosition) {
            return {
              ...node,
              position: savedPosition
            };
          }
          return node;
        });
        
        setNodes(nodesWithSavedPositions as any);
      } else {
        setNodes(flowData.nodes as any);
      }
      
      setEdges(flowData.edges as any);
      setWorkflowMetadata(flowData.metadata);
    }
    
    fetchAndConvert();
  }, [selected]);
  
  // Handle workflow metadata updates
  const updateWorkflowMetadata = async (updatedMetadata: WorkflowMetadata) => {
    if (!selected) return;
    
    try {
      // Send updated metadata to the backend
      const response = await fetch('http://localhost:8000/api/workflows/update-metadata', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: selected,
          metadata: updatedMetadata
        }),
      });
      
      if (response.ok) {
        // Update local state
        setWorkflowMetadata(updatedMetadata);
      } else {
        console.error('Failed to update workflow metadata');
      }
    } catch (error) {
      console.error('Error updating workflow metadata:', error);
    }
  };

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
        onUpdateMetadata={updateWorkflowMetadata}
        allWorkflowsMetadata={allWorkflowsMetadata}
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
                onClick={() => {
                  setAllWorkflowsMetadata({});
                  fetchWorkflows();
                  if (selected) fetchWorkflow(selected);
                }}
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
