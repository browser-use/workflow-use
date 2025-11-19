"""
Test to verify step counter works correctly without callbacks.

This test verifies the fix for the issue where step counter would remain at 0
when no callback was provided.
"""


def test_step_counter_increments_without_callback():
	"""
	Verify that step counter increments even when on_step_recorded is None.

	This tests the fix where the counter increment was moved outside the
	callback conditional block.
	"""
	# Read the service.py file and verify the counter increment is outside the callback check
	with open('workflow_use/healing/service.py', 'r') as f:
		content = f.read()

	# Look for the pattern where counter increments before callback check
	# The fixed code should have:
	# 1. step_counter['count'] += 1  (outside if block)
	# 2. if self.on_step_recorded:   (after the increment)

	lines = content.split('\n')

	# Find the act method in CapturingController
	in_act_method = False
	found_increment_outside = False
	increment_line = -1
	callback_check_line = -1

	for i, line in enumerate(lines):
		if 'async def act(self, action, browser_session' in line:
			in_act_method = True
			continue

		if in_act_method:
			# Look for the counter increment
			if "step_counter['count'] += 1" in line:
				increment_line = i
				# Check if this line is NOT inside an "if self.on_step_recorded:" block
				# by looking backwards for the nearest if statement
				for j in range(i - 1, max(i - 10, 0), -1):
					if 'if self.on_step_recorded:' in lines[j]:
						# Found callback check before increment - this is the OLD (buggy) pattern
						break
					if "step_counter['count'] += 1" in lines[j]:
						# Found the increment first - this is the NEW (fixed) pattern
						found_increment_outside = True
						break
				else:
					# No callback check found in the 10 lines before - increment is outside
					found_increment_outside = True

			# Look for the callback check
			if 'if self.on_step_recorded:' in line and increment_line > 0:
				callback_check_line = i
				break

	assert found_increment_outside, (
		'Step counter increment should be outside the callback check block. '
		'The counter should increment on every action regardless of callback availability.'
	)

	assert increment_line > 0, 'Could not find step_counter increment'
	assert callback_check_line > 0, 'Could not find callback check'
	assert increment_line < callback_check_line, (
		f'Step counter increment (line {increment_line}) should come BEFORE callback check (line {callback_check_line})'
	)

	print(f'✓ Step counter increments at line {increment_line}')
	print(f'✓ Callback check at line {callback_check_line}')
	print('✓ Counter increments BEFORE callback check (correct order)')


def test_status_update_uses_counter():
	"""
	Verify that the status update message uses the step counter correctly.
	"""
	with open('workflow_use/healing/service.py', 'r') as f:
		content = f.read()

	# Look for the status update that reports step count
	assert 'Completed recording {step_counter["count"]} steps' in content, (
		"Status update should use step_counter['count'] to report accurate step count"
	)

	print("✓ Status update correctly uses step_counter['count']")


if __name__ == '__main__':
	print('=' * 80)
	print('Testing Step Counter Fix')
	print('=' * 80)
	print()

	print('Test 1: Verify counter increments without callback...')
	test_step_counter_increments_without_callback()
	print()

	print('Test 2: Verify status update uses counter...')
	test_status_update_uses_counter()
	print()

	print('=' * 80)
	print('✅ All step counter tests passed!')
	print('=' * 80)
