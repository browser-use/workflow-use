import os

AGENT_STEP_SYSTEM_PROMPT = open(os.path.join(os.path.dirname(__file__), 'prompts', 'agent_step_system_prompt.md')).read()


WORKFLOW_FALLBACK_PROMPT_TEMPLATE = (
	'While executing step {step_index}/{total_steps} in the workflow:\n\n'
	# "{workflow_details}\n\n"
	"The deterministic action '{action_type}' failed with the following context:\n"
	'{fail_details}\n\n'
	'The intended target or expected value for this step was: {failed_value}\n\n'
	'IMPORTANT: Your task is to ONLY complete this specific step ({step_index}) and nothing more. '
	"The step's purpose is described as: '{step_description}'.\n"
	'Do not retry the same action that failed. Instead, choose a different suitable action(s) to accomplish the same goal. '
	'For example, if a click failed, consider navigating to a URL, inputting text, or selecting an option. '
	'However, ONLY perform the minimum action needed to complete this specific step. '
	'If the step requires clicking a button, ONLY click that button. If it requires navigation, ONLY navigate. '
	'Do not perform any additional actions beyond what is strictly necessary for this step. '
	'Once the objective of step {step_index} is reached, call the Done action to complete the step. '
	'Do not proceed to the next step or perform any actions beyond this specific step.'
)

STRUCTURED_OUTPUT_PROMPT = """
You are a data extraction expert. Your task is to extract structured information from the provided content.

The content may contain various pieces of information from different sources. You need to analyze this content and extract the relevant information according to the output schema provided below.

Only extract information that is explicitly present in the content. Be precise and follow the schema exactly.
"""
