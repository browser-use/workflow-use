import React, { useState, ChangeEvent } from "react";
import {
  Workflow,
  WorkflowItemProps,
} from "../types/workflow-layout.types";

const WorkflowItem: React.FC<WorkflowItemProps> = ({
  id,
  selected,
  workflow,
  onSelect,
  onUpdateWorkflow,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [edited, setEdited] = useState<Workflow | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const displayName = () => {
    if (workflow)
      return (
        <>
          <span className="text-md">{workflow.name}</span>
          {workflow.version && (
            <span className="text-xs text-[#888] ml-1.5">
              v{workflow.version}
            </span>
          )}
        </>
      );
    return <span className="text-md">{id}</span>;
  };

  const change = 
    (field: keyof Workflow) => 
    (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      if (!edited) return;
      setEdited({ ...edited, [field]: e.target.value });
    };

  const save = async () => {
    if (!edited) return;
    setSubmitting(true);
    await onUpdateWorkflow(edited).finally(() => setSubmitting(false));
    setIsEditing(false);
  };

  const editForm = workflow && (
    <div>
      {(["name", "version"] as const).map((f) => (
        <label key={f} className="block text-xs mb-2">
          <span className="block text-[#aaa] mb-1">
            {f[0]?.toUpperCase() + f.slice(1)}
          </span>
          <input
            className="w-full bg-[#333] border border-[#555] text-white p-1.5 rounded text-xs"
            value={edited?.[f] ?? ""}
            onChange={change(f as keyof Workflow)}
          />
        </label>
      ))}

      <label className="block text-xs mb-2">
        <span className="block text-[#aaa] mb-1">Description</span>
        <textarea
          className="w-full bg-[#333] border border-[#555] text-white p-1.5 rounded min-h-[60px] resize-y text-xs"
          value={edited?.description ?? ""}
          onChange={change("description")}
        />
      </label>

      <div className="flex gap-2 justify-end">
        <button
          onClick={() => setIsEditing(false)}
          className="bg-[#444] text-white py-1.5 px-3 rounded text-xs"
        >
          Cancel
        </button>
        <button
          disabled={submitting}
          onClick={save}
          className={`bg-blue-400 hover:bg-blue-500 text-white py-1.5 px-3 rounded text-xs ${
            submitting && "opacity-70"
          }`}
        >
          {submitting ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );

  const readOnly = workflow && (
    <>
      <div className="mb-2">
        <div className="text-xs text-[#aaa] mb-1">Description</div>
        <div className="text-xs">{workflow.description}</div>
      </div>

      {Array.isArray(workflow.input_schema) && workflow.input_schema.length > 0 && (
        <>
          <div className="text-xs text-[#aaa] mb-1">Input Parameters</div>
          <ul className="pl-4 text-xs list-disc marker:text-[#7ac5ff]">
            {workflow.input_schema.map((p) => (
              <li key={p.name} className="mb-1">
                <span className="text-[#7ac5ff]">{p.name}</span>
                <span className="text-[#aaa]"> ({p.type})</span>
                {p.required && <span className="text-[#ff7a7a]"> *</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );

  return (
    <>
      {/* row button */}
      <li>
        <button
          className={`w-full text-left py-1.5 ${
            selected ? "font-semibold text-[#7ac5ff]" : "text-[#ccc]"
          }`}
          onClick={() => onSelect(id)}
        >
          {displayName()}
        </button>
      </li>

      {/* details panel */}
      {selected && workflow && (
        <li className="py-2 pl-4 border-l border-[#444] my-1 ml-1">
          <div className="flex justify-between items-center mb-2">
            <h4 className="m-0 text-sm text-[#ddd]">Details</h4>
            {!isEditing && (
              <button
                onClick={() => {
                  setEdited({ ...workflow });
                  setIsEditing(true);
                }}
                className="bg-[#444] text-white py-1 px-2 rounded text-xs"
              >
                Edit
              </button>
            )}
          </div>
          {isEditing ? editForm : readOnly}
        </li>
      )}
    </>
  );
};

export default WorkflowItem;
