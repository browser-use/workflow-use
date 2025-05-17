import React from 'react';
import { SidebarProps } from '../types/sidebar.types';
import WorkflowItem from './workflow-item';

export const Sidebar: React.FC<SidebarProps> = ({
  workflows,
  onSelect,
  selected,
  workflowMetadata,
  onUpdateMetadata,
  allWorkflowsMetadata = {},
}) => (
  <aside className="w-[250px] border-r border-[#444] p-3 bg-[#2a2a2a] text-white flex flex-col overflow-auto">
    {/* logo */}
    <div className="flex justify-center mb-4">
      <img
        src="/browseruse.png"
        alt="Browser Use Logo"
        className="max-w-[80%] max-h-[60px]"
      />
    </div>
    
    <h3 className="text-lg text-[#ddd]">Workflows</h3>

    <ul className="m-0 p-0">
      {workflows.map((id) => (
        <WorkflowItem
          key={id}
          id={id}
          selected={id === selected}
          metadata={
            id === selected
            ? workflowMetadata ?? undefined
            : allWorkflowsMetadata[id]
          }
          onSelect={onSelect}
          onUpdateMetadata={onUpdateMetadata}
        />
      ))}
    </ul>
  </aside>
);

export default Sidebar;