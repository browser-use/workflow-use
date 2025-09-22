import React from "react";
import WorkflowItem from "./workflow-item";
import { SidebarProps } from "../types/sidebar.types";

export const Sidebar: React.FC<SidebarProps> = ({
  onSelect,
  selected,
  workflowsData,
  onUpdateWorkflow,
}) => (
  <aside className="w-[250px] border-r border-[#542e2e] p-3 bg-[#2a2a2a] text-white flex flex-col overflow-auto">
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
      {Object.keys(workflowsData).map((id) => (
        <WorkflowItem
          key={id}
          id={id}
          selected={id === selected}
          workflow={workflowsData[id]}
          onSelect={onSelect}
          onUpdateWorkflow={(workflow) => onUpdateWorkflow(id, workflow)}
        />
      ))}
    </ul>
  </aside>
);

export default Sidebar;
