# WORKFLOW_FALLBACK_PROMPT_TEMPLATE = (
#     "While executing step {step_index}/{total_steps} in the workflow:\n\n{workflow_details}\n\n"
#     "The deterministic action failed with the following context:\n{fail_details}\n\n"
#     "The value that was expected to be inputted, clicked or navigated to based on the step description was: {failed_value}\n\n"
#     "Please analyze the situation and achieve the objective of step {step_index} using the available browser actions. "
#     "You do not have to use the same action – feel free to choose any suitable action(s) to accomplish the same goal. "
#     "Once the objective of step {step_index} is reached, call the Done action to complete the step."
#     "Do not attempt to use the same action again – choose a different one."
#     "Do not continue with the next step, just complete step {step_index}."
# )
WORKFLOW_FALLBACK_PROMPT_TEMPLATE = (
    "While executing step {step_index}/{total_steps} in the workflow:\n\n"
    "{workflow_details}\n\n"
    "The deterministic action '{action_type}' failed with the following context:\n"
    "{fail_details}\n\n"
    "The intended target or expected value for this step was: {failed_value}\n\n"
    "Please analyze the situation and achieve the objective of step {step_index} using the available browser actions. "
    "The step's purpose is described as: '{step_description}'.\n"
    "Do not retry the same action that failed. Instead, choose a different suitable action(s) to accomplish the same goal. "
    "For example, if a click failed, consider navigating to a URL, inputting text, or selecting an option. "
    "Once the objective of step {step_index} is reached, call the Done action to complete the step. "
    "Do not proceed to the next step; focus only on completing step {step_index}."
    "The user has also provided the following custom instructions: {agent_custom_instructions}\n"
)