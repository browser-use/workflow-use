#!/usr/bin/env python3
"""
Test script to verify the max_alternatives bug fix.

Bug: When max_alternatives=1, the function was returning 2 XPaths instead of 1.
Fix: Now correctly returns only the absolute xpath when max_alternatives <= 1.
"""

from workflow_use.healing.xpath_optimizer import XPathOptimizer

optimizer = XPathOptimizer()

absolute_xpath = '/html/body/form/div[3]/table/tbody/tr[2]/td[3]/a'
element_info = {
	'tag': 'a',
	'text': 'License 12345',
	'attributes': {'class': 'license-link', 'href': '/license/12345'},
}

print('=' * 80)
print('Testing max_alternatives Bug Fix')
print('=' * 80)

# Test max_alternatives = 1
print('\n📋 Test 1: max_alternatives=1')
print(f'   Input: {absolute_xpath}')
result_1 = optimizer.optimize_xpath(absolute_xpath, element_info, max_alternatives=1)
print('   Expected: 1 XPath (only absolute)')
print(f'   Got: {len(result_1)} XPath(s)')
print('   XPaths:')
for i, xpath in enumerate(result_1, 1):
	print(f'      {i}. {xpath}')

# Validate: Should be exactly 1 XPath and it should be the absolute one
test_1_pass = len(result_1) == 1 and result_1[0] == absolute_xpath
if test_1_pass:
	print('   ✅ PASS: Exactly 1 XPath returned (absolute)')
else:
	print(f'   ❌ FAIL: Expected 1 absolute XPath, got {len(result_1)}')
	if len(result_1) > 0 and result_1[0] != absolute_xpath:
		print('   ❌ FAIL: First XPath is not the absolute one!')

# Test max_alternatives = 2
print('\n📋 Test 2: max_alternatives=2')
print(f'   Input: {absolute_xpath}')
result_2 = optimizer.optimize_xpath(absolute_xpath, element_info, max_alternatives=2)
print('   Expected: 2 XPaths (1 optimized + 1 absolute)')
print(f'   Got: {len(result_2)} XPath(s)')
print('   XPaths:')
for i, xpath in enumerate(result_2, 1):
	is_absolute = xpath == absolute_xpath
	print(f'      {i}. {xpath[:60]}{"..." if len(xpath) > 60 else ""} {"(absolute)" if is_absolute else "(optimized)"}')

# Validate: Should be 2 XPaths, last one should be absolute, first should be optimized
test_2_pass = (
	len(result_2) == 2
	and result_2[-1] == absolute_xpath  # Last is absolute
	and result_2[0] != absolute_xpath  # First is optimized (different from absolute)
)
if test_2_pass:
	print('   ✅ PASS: Exactly 2 XPaths (1 optimized + 1 absolute)')
else:
	print(f'   ❌ FAIL: Expected 2 XPaths (1 optimized + 1 absolute), got {len(result_2)}')
	if len(result_2) >= 2 and result_2[-1] != absolute_xpath:
		print('   ❌ FAIL: Last XPath is not the absolute fallback!')
	if len(result_2) >= 1 and result_2[0] == absolute_xpath:
		print('   ❌ FAIL: First XPath should be optimized, not absolute!')

# Test max_alternatives = 3
print('\n📋 Test 3: max_alternatives=3')
print(f'   Input: {absolute_xpath}')
result_3 = optimizer.optimize_xpath(absolute_xpath, element_info, max_alternatives=3)
print('   Expected: 3 XPaths (2 optimized + 1 absolute)')
print(f'   Got: {len(result_3)} XPath(s)')
print('   XPaths:')
for i, xpath in enumerate(result_3, 1):
	is_absolute = xpath == absolute_xpath
	print(f'      {i}. {xpath[:60]}{"..." if len(xpath) > 60 else ""} {"(absolute)" if is_absolute else "(optimized)"}')

# Validate: Should be 3 XPaths, last one absolute, first two optimized
optimized_count = sum(1 for xpath in result_3[:-1] if xpath != absolute_xpath)
test_3_pass = (
	len(result_3) == 3
	and result_3[-1] == absolute_xpath  # Last is absolute
	and optimized_count >= 1  # At least 1 optimized (ideally 2)
	and all(xpath != absolute_xpath for xpath in result_3[:-1])  # All except last are different from absolute
)
if test_3_pass:
	print(f'   ✅ PASS: Exactly 3 XPaths ({optimized_count} optimized + 1 absolute)')
else:
	print(f'   ❌ FAIL: Expected 3 XPaths (2 optimized + 1 absolute), got {len(result_3)}')
	if len(result_3) >= 3 and result_3[-1] != absolute_xpath:
		print('   ❌ FAIL: Last XPath is not the absolute fallback!')
	if len(result_3) >= 2:
		non_optimized = sum(1 for xpath in result_3[:-1] if xpath == absolute_xpath)
		if non_optimized > 0:
			print(f'   ❌ FAIL: Found {non_optimized} non-optimized XPath(s) before the final absolute!')

# Summary
print('\n' + '=' * 80)
all_pass = test_1_pass and test_2_pass and test_3_pass
if all_pass:
	print('🎉 All tests passed! Bug is fixed.')
	print('   • max_alternatives=1: Returns only absolute XPath ✅')
	print('   • max_alternatives=2: Returns 1 optimized + 1 absolute ✅')
	print('   • max_alternatives=3: Returns 2 optimized + 1 absolute ✅')
else:
	print('❌ Some tests failed. Bug still exists.')
	if not test_1_pass:
		print('   • Test 1 (max_alternatives=1) FAILED')
	if not test_2_pass:
		print('   • Test 2 (max_alternatives=2) FAILED')
	if not test_3_pass:
		print('   • Test 3 (max_alternatives=3) FAILED')
print('=' * 80)
