
import os
import asyncio
import requests
from typing import Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from browser_use.controller.service import Controller
from workflow_use.workflow.service import Workflow
from workflow_use.workflow.service import ActionResult

controller = Controller()

llm_instance = None
try:
    llm_instance = ChatOpenAI(model='gpt-4o')
except Exception as e:
    print(f'Error initializing LLM: {e}. Would you like to set your OPENAI_API_KEY?')
    set_openai_api_key = input('Set OPENAI_API_KEY? (y/n): ')
    if set_openai_api_key.lower() == 'y':
        os.environ['OPENAI_API_KEY'] = input('Enter your OPENAI_API_KEY: ')
        llm_instance = ChatOpenAI(model='gpt-4o')

class NotificationParams(BaseModel):
    error: Optional[str] = Field(default=None, description="Error message")
    step: Optional[str] = Field(default=None, description="Step name")
    step_description: Optional[str] = Field(default=None, description="Step description")
    plan: Optional[str] = Field(default=None, description="Agent's plan to resolve the error")

@controller.registry.action(
    'Notify Discord of Workflow Error',
    param_model=NotificationParams,
)
async def notify_discord_of_workflow_error(params: NotificationParams):
    print(f"Notifying Discord of workflow error: {params.error}")
    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("WEBHOOK_URL environment variable is not set")
    
    message = f'''
    Error occurred in workflow:
    ```
{params.error}

On step: {params.step}

Description: {params.step_description}

Plan: {params.plan}
    ```
    '''
    try:
        response = requests.post(webhook_url, json={"content": message}, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to notify Discord: {e}")

    return ActionResult(extracted_content=message, include_in_memory=True)

async def main():
    agent_custom_instructions = "Before attempting to resolve the step, use the notify discord of workflow error action to notify discord of the error."
    workflow = Workflow.load_from_file(
        'examples/custom-action/workflow.json', 
        llm=llm_instance,
        agent_controller=controller,
        agent_custom_instructions=agent_custom_instructions,
    )

    ticket_number = '123456789'
    license_plate = 'ABC123'

    await workflow.run(
        inputs={'ticket_number': ticket_number, 'license_plate': license_plate},
        close_browser_at_end=False,
    )

if __name__ == '__main__':
    asyncio.run(main())
