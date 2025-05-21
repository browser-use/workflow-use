# Multi-Agent Workflow Orchestrator with MCP and Gemini Integration

## Overview
This update introduces a robust multi-agent workflow orchestrator that leverages the Model Context Protocol (MCP) for secure, auditable, and flexible agent communication. The orchestrator now supports Google Gemini as an agent, allowing users to run advanced AI workflows with configurable LLMs.

## Key Features & Changes

- **MCP-Compliant Orchestrator**: Implements a FastAPI-based orchestrator that manages workflows composed of multiple agents. Each agent communicates via an MCP endpoint, ensuring interoperability and traceability.
- **Google Gemini Agent Integration**: Adds support for Google Gemini as an agent. The Gemini API key is configurable via the `GEMINI_API_KEY` environment variable (use `YOURGEMINIAPIKEY` as a placeholder in documentation and code examples).
- **Configurable Agent Endpoints**: Each agent in a workflow can specify its own MCP endpoint, making the orchestrator extensible to other LLMs or agent types.
- **Workflow Launch & Monitoring**: Provides endpoints to launch new workflows, monitor their status, and retrieve results. Workflows are tracked with unique IDs and detailed step information.
- **Real-World Example**: Demonstrates a workflow where a Gemini agent summarizes AI research trends for 2025, including citations, using the latest Gemini model.
- **Security & Best Practices**: API keys are never hardcoded in documentation or code. Use `YOURGEMINIAPIKEY` as a placeholder and set the real key via environment variables.

## How MCP is Used
- **Agent Communication**: Each agent is defined with an `mcp_endpoint` (e.g., Gemini's REST API endpoint). The orchestrator sends tasks and context to these endpoints using the MCP, ensuring a standardized protocol for agent interaction.
- **Extensibility**: By following MCP, the orchestrator can easily integrate with other compliant agents or LLMs in the future.

## Example Workflow
- **Launch**: POST to `/api/enterprise/workflows/launch` with a payload specifying a Gemini agent and task.
- **Monitor**: GET `/api/enterprise/workflows/{workflow_id}` to check status and retrieve results.
- **Result**: The Gemini agent returns a detailed summary with citations, as shown in the included screenshot.

## Files Added/Changed
- `workflows/workflow_use/orchestrator/mcp_orchestrator.py`: Implements the orchestrator and MCP logic.
- `workflows/cli.py`: Integrates the orchestrator and configures Gemini as an agent.
- `workflows/test_gemini_workflow.py`: Example test script for launching a Gemini workflow.
- `workflows/gemini_workflow_success.md`: Documents the successful workflow run and includes the screenshot.
- `workflows/gemini_workflow_success.png`: Screenshot of a successful Gemini workflow execution.
- `workflows/gemini_orchestrator_changes.md`: **(this file)** Detailed summary of all changes and rationale.

1. Orchestrator and MCP Usage
/workspaces/workflow-use/workflows/workflow_use/orchestrator/mcp_orchestrator.py

Implements the multi-agent workflow orchestrator.
Explicitly mentions MCP (Model Context Protocol) in comments and docstrings:
# mcp_orchestrator.py
# MCP-compliant Multi-Agent Workflow Orchestrator
# This service allows launching, managing, and monitoring workflows composed of multiple AI agents, each communicating securely via the Model Context Protocol (MCP).
Handles agent configuration, including mcp_endpoint for each agent:
class AgentConfig(BaseModel):
    ...
    mcp_endpoint: str
Handles Gemini API integration and key management:
gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "YOURGEMINIAPIKEY")
...
if "gemini" in step.agent.tools[0].lower():
    api_url = step.agent.mcp_endpoint.replace("API_KEY", step.gemini_api_key)
2. Gemini Integration and Example
/workspaces/workflow-use/workflows/cli.py

Sets up the Gemini API key and default LLM if OpenAI is not configured:
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOURGEMINIAPIKEY")
...
class GeminiLLM:
    ...
    self.model = "gemini-2.5-flash-preview-05-20"
/workspaces/workflow-use/workflows/test_gemini_workflow.py

Contains a test for launching a workflow with a Gemini agent and MCP endpoint.

---

For more details, see the included markdown and screenshot files.
3. Documentation and Summary of Changes
/workspaces/workflow-use/workflows/gemini_workflow_success.md

Documents the feature, including:
Screenshot of successful POST/GET to /api/enterprise/workflows/launch and /api/enterprise/workflows/{id}
Description of the workflow, Gemini agent, and MCP usage
Example: AI research trends summary with citations using Gemini 2.5
/workspaces/workflow-use/workflows/gemini_workflow_success.png

Screenshot showing successful workflow execution and result retrieval.
