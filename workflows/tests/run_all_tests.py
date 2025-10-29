"""
Run all unit tests for the semantic-only workflow system.

This script runs all test modules and provides a summary.
"""

import subprocess
import sys


def run_test_file(test_file):
	"""Run a single test file and return (passed, failed)"""
	print(f'\n{"=" * 80}')
	print(f'Running {test_file}')
	print(f'{"=" * 80}')

	result = subprocess.run(['uv', 'run', 'python', f'workflows/tests/{test_file}'], capture_output=True, text=True)

	# Print output
	print(result.stdout)
	if result.stderr:
		print(result.stderr)

	# Parse results from output
	for line in result.stdout.split('\n'):
		if 'Test Results:' in line:
			# Extract passed and failed counts
			# Format: "Test Results: X passed, Y failed"
			parts = line.split(':')[1].strip().split(',')
			passed = int(parts[0].split()[0])
			failed = int(parts[1].split()[0])
			return (passed, failed)

	# If we couldn't parse, check exit code
	if result.returncode == 0:
		return (1, 0)  # Assume some tests passed
	else:
		return (0, 1)  # Assume some tests failed


def main():
	"""Run all tests and provide summary"""
	test_files = [
		'test_selector_generator.py',
		'test_element_finder.py',
		'test_workflow_execution.py',
	]

	print('\n' + '=' * 80)
	print('SEMANTIC-ONLY WORKFLOW SYSTEM - UNIT TEST SUITE')
	print('=' * 80)

	total_passed = 0
	total_failed = 0

	results = []

	for test_file in test_files:
		passed, failed = run_test_file(test_file)
		total_passed += passed
		total_failed += failed
		results.append((test_file, passed, failed))

	# Print summary
	print('\n' + '=' * 80)
	print('TEST SUITE SUMMARY')
	print('=' * 80)

	for test_file, passed, failed in results:
		status = '✅ PASS' if failed == 0 else '❌ FAIL'
		print(f'{status} {test_file:40s} {passed:3d} passed, {failed:3d} failed')

	print(f'\n{"=" * 80}')
	print(f'TOTAL: {total_passed} passed, {total_failed} failed')
	print(f'{"=" * 80}\n')

	if total_failed > 0:
		print('❌ Some tests failed!')
		sys.exit(1)
	else:
		print('✅ All tests passed!')
		sys.exit(0)


if __name__ == '__main__':
	main()
