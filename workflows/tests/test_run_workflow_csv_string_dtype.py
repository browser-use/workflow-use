"""Regression test for run-workflow-csv string inputs (leading zeros, NA/null tokens).

Exercises the real helpers in workflow_use.csv_inputs that run_workflow_csv_command uses. Before the
fix, pd.read_csv inferred numeric dtypes and applied default NA detection, so string-typed inputs
like a zip "01234" or country code "NA" were corrupted or silently dropped. The helpers live in a
light module so this test needs no browser_use.
"""

import io
import sys

import pandas as pd

from workflow_use.csv_inputs import convert_csv_value, is_missing, load_workflow_csv

CSV = 'zip,code,count,flag,note\n01234,NA,1002,true,hello\n00089,null,7,false,world\n'


def test_string_fields_keep_exact_text():
	df = load_workflow_csv(io.StringIO(CSV))
	assert convert_csv_value(df.iloc[0]['zip'], 'string') == '01234'  # leading zero kept
	assert convert_csv_value(df.iloc[1]['zip'], 'string') == '00089'
	assert convert_csv_value(df.iloc[0]['code'], 'string') == 'NA'  # Namibia, not NaN
	assert convert_csv_value(df.iloc[1]['code'], 'string') == 'null'  # literal, not NaN
	assert convert_csv_value(df.iloc[0]['note'], 'string') == 'hello'


def test_number_and_bool_fields_still_convert():
	df = load_workflow_csv(io.StringIO(CSV))
	assert convert_csv_value(df.iloc[0]['count'], 'number') == 1002.0
	assert convert_csv_value(df.iloc[0]['flag'], 'bool') is True
	assert convert_csv_value(df.iloc[1]['flag'], 'bool') is False


def test_empty_required_cell_detected_missing():
	# An empty cell must stay NaN so the caller's required-field pd.isna() check still fires.
	df = load_workflow_csv(io.StringIO('zip,count\n,5\n'))
	assert pd.isna(df.iloc[0]['zip'])


def test_missing_is_type_aware():
	# NA tokens are missing for numeric/bool fields (cannot be a number) but literal text for strings.
	assert is_missing('NA', 'string') is False  # Namibia, kept
	assert is_missing('null', 'string') is False
	assert is_missing('NA', 'number') is True  # would-be numeric NA -> missing, not a hard error
	assert is_missing('null', 'bool') is True
	assert is_missing('01234', 'number') is False
	assert is_missing(float('nan'), 'string') is True  # empty cell always missing


def _run() -> int:
	tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
	passed = failed = 0
	for t in tests:
		try:
			t()
			print(f'PASS: {t.__name__}')
			passed += 1
		except Exception as e:
			print(f'FAIL: {t.__name__}: {e}')
			failed += 1
	print(f'Test Results: {passed} passed, {failed} failed')
	return failed


if __name__ == '__main__':
	sys.exit(1 if _run() else 0)
