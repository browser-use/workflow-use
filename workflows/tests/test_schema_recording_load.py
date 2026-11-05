"""Load Chrome recorder JSON without requiring a trailing extract step."""

from workflow_use.schema.views import ClickStep, WorkflowDefinitionSchema


def _chrome_recording_payload(*, last_step_type: str = 'click') -> dict:
	last_step: dict
	if last_step_type == 'click':
		last_step = {
			'type': 'click',
			'targetText': 'Order with Careem',
			'url': 'https://www.ubereats.com/feed',
		}
	else:
		last_step = {'type': 'extract', 'extractionGoal': 'Get confirmation'}

	return {
		'name': 'Recorded Workflow (Semantic)',
		'description': 'Recorded on 8/29/2026, 5:50:27 PM',
		'version': '1.0',
		'input_schema': [],
		'steps': [
			{'type': 'navigation', 'url': 'https://www.ubereats.com/feed'},
			last_step,
		],
	}


def test_chrome_recording_ending_in_click_loads():
	workflow = WorkflowDefinitionSchema.model_validate(_chrome_recording_payload())

	assert len(workflow.steps) == 2
	assert workflow.steps[-1].type == 'click'
	assert isinstance(workflow.steps[-1], ClickStep)
	assert workflow.steps[-1].target_text == 'Order with Careem'


def test_snake_case_target_text_still_loads():
	workflow = WorkflowDefinitionSchema.model_validate(
		{
			'name': 'Semantic workflow',
			'description': 'Hand-written',
			'version': '1.0',
			'input_schema': [],
			'steps': [
				{'type': 'navigation', 'url': 'https://example.com'},
				{'type': 'click', 'target_text': 'Submit'},
			],
		}
	)

	assert workflow.steps[-1].target_text == 'Submit'


def test_extract_ending_workflow_still_loads():
	workflow = WorkflowDefinitionSchema.model_validate(_chrome_recording_payload(last_step_type='extract'))

	assert workflow.steps[-1].type == 'extract'
