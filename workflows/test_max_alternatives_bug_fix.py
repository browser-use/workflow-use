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

if len(result_1) == 1:
	print('   ✅ PASS: Exactly 1 XPath returned')
else:
	print(f'   ❌ FAIL: Expected 1, got {len(result_1)}')

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

if len(result_2) == 2:
	print('   ✅ PASS: Exactly 2 XPaths returned')
else:
	print(f'   ❌ FAIL: Expected 2, got {len(result_2)}')

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

if len(result_3) == 3:
	print('   ✅ PASS: Exactly 3 XPaths returned')
else:
	print(f'   ❌ FAIL: Expected 3, got {len(result_3)}')

# Summary
print('\n' + '=' * 80)
all_pass = len(result_1) == 1 and len(result_2) == 2 and len(result_3) == 3
if all_pass:
	print('🎉 All tests passed! Bug is fixed.')
else:
	print('❌ Some tests failed. Bug still exists.')
print('=' * 80)
