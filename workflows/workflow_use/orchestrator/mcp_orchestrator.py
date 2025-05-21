# mcp_orchestrator.py
"""
 MCP-compliant Multi-Agent Workflow Orchestrator

This service allows launching, managing, and monitoring workflows composed of multiple AI agents, each communicating securely via the Model Context Protocol (MCP).
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import uuid
import datetime
import os
import requests

# --- Models ---

class AgentConfig(BaseModel):
    name: str
    role: str
    tools: List[str] = []
    mcp_endpoint: str
    context: Optional[Dict[str, Any]] = None

class WorkflowStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent: AgentConfig
    task: str
    status: str = "pending"
    result: Optional[Any] = None
    started_at: Optional[datetime.datetime] = None
    finished_at: Optional[datetime.datetime] = None
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "YOURGEMINIAPIKEY")  # Add Gemini API key to each step (optional, can be overridden)

class WorkflowInstance(BaseModel):
    workflow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    steps: List[WorkflowStep]
    status: str = "created"
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

# --- In-memory store (for demo) ---
workflows: Dict[str, WorkflowInstance] = {}

# --- API Router ---
router = APIRouter()

@router.post("/workflows/launch", response_model=WorkflowInstance)
def launch_workflow(wf: WorkflowInstance, background_tasks: BackgroundTasks):
    workflows[wf.workflow_id] = wf
    wf.status = "running"
    wf.updated_at = datetime.datetime.utcnow()
    background_tasks.add_task(run_workflow, wf.workflow_id)
    return wf

@router.get("/workflows/{workflow_id}", response_model=WorkflowInstance)
def get_workflow(workflow_id: str):
    if workflow_id not in workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflows[workflow_id]

@router.get("/workflows", response_model=List[WorkflowInstance])
def list_workflows():
    return list(workflows.values())

# --- Orchestration Logic ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOURGEMINIAPIKEY")

def run_workflow(workflow_id: str):
    wf = workflows[workflow_id]
    for step in wf.steps:
        step.status = "running"
        step.started_at = datetime.datetime.utcnow()
        # If the agent is Gemini, call the Gemini API endpoint
        if "gemini" in step.agent.tools[0].lower():
            payload = {
                "contents": [{"parts": [{"text": step.agent.context.get("prompt", step.task)}]}]
            }
            headers = {"Content-Type": "application/json"}
            api_url = step.agent.mcp_endpoint.replace("API_KEY", step.gemini_api_key)
            try:
                resp = requests.post(api_url, json=payload, headers=headers)
                step.result = resp.json()
            except Exception as e:
                step.result = f"Gemini API error: {e}"
        else:
            # Simulate result for non-Gemini agents
            step.result = f"Simulated result for {step.agent.name} on task: {step.task}"
        step.status = "completed"
        step.finished_at = datetime.datetime.utcnow()
        wf.updated_at = datetime.datetime.utcnow()
    wf.status = "completed"
    wf.updated_at = datetime.datetime.utcnow()

# --- To integrate: import and include router in your FastAPI app ---
# from .mcp_orchestrator import router as mcp_router
# app.include_router(mcp_router, prefix="/api/enterprise")
