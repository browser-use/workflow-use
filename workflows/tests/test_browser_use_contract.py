"""API-contract tests between workflow-use and the pinned browser-use version.

workflow-use replays workflows through browser-use's CDP actor API. Historically the
engine was written against Playwright's API (page.locator, wait_for_selector,
page.check, query_selector_all, ...) which does NOT exist on the CDP actor surface —
every such call raises AttributeError at runtime, usually swallowed by broad excepts,
so entire subsystems fail silently.

These tests are import-time only (no browser is launched) and guard both directions:

1. ``TestCdpSurfaceContract`` — every browser-use attribute the engine relies on must
   exist with a compatible signature. If a browser-use upgrade changes the surface,
   this fails at CI time instead of silently at replay time.
2. ``TestNoPlaywrightIsms`` — a static scan asserting the engine never calls
   Playwright-only APIs outside the dedicated CDP compatibility layer
   (``workflow_use/compat/cdp.py``). This prevents the bug class from regressing.

Run with: ``uv run pytest tests/test_browser_use_contract.py``
"""

import inspect
import re
from pathlib import Path

from browser_use import Browser
from browser_use.actor.element import Element
from browser_use.actor.page import Page
from browser_use.dom.views import EnhancedDOMTreeNode
from browser_use.llm.views import ChatInvokeCompletion
from browser_use.tools.service import Tools

WORKFLOW_USE_ROOT = Path(__file__).resolve().parent.parent / 'workflow_use'


class TestCdpSurfaceContract:
	"""Everything the replay engine calls on browser-use must exist."""

	def test_page_methods_exist(self):
		required = [
			'goto',
			'evaluate',
			'press',
			'get_elements_by_css_selector',
			'get_url',
			'get_title',
			'screenshot',
			'must_get_element_by_prompt',
		]
		missing = [name for name in required if not hasattr(Page, name)]
		assert not missing, f'browser-use Page lost methods the engine depends on: {missing}'

	def test_element_methods_exist(self):
		required = ['click', 'fill', 'focus', 'check', 'select_option', 'evaluate', 'get_attribute', 'hover', 'get_bounding_box']
		missing = [name for name in required if not hasattr(Element, name)]
		assert not missing, f'browser-use Element lost methods the engine depends on: {missing}'

	def test_browser_session_methods_exist(self):
		required = ['start', 'stop', 'get_current_page', 'get_browser_state_summary', 'get_selector_map']
		missing = [name for name in required if not hasattr(Browser, name)]
		assert not missing, f'browser-use Browser lost methods the engine depends on: {missing}'

	def test_element_click_takes_no_force_kwarg(self):
		"""Element.click has (button, click_count, modifiers) — Playwright's force= must not be passed."""
		params = inspect.signature(Element.click).parameters
		assert 'force' not in params, 'Element.click grew a force= kwarg; revisit cdp compat layer'
		assert 'button' in params and 'click_count' in params

	def test_element_select_option_takes_values_only(self):
		"""Element.select_option accepts values only — Playwright's label=/index= do not exist."""
		params = list(inspect.signature(Element.select_option).parameters)
		assert params == ['self', 'values'], f'Element.select_option signature changed: {params}'

	def test_page_evaluate_returns_json_string(self):
		"""Page.evaluate JSON-stringifies results — callers must json.loads, never treat as dict."""
		sig = inspect.signature(Page.evaluate)
		assert sig.return_annotation in ('str', str), f'Page.evaluate return annotation changed: {sig.return_annotation}'

	def test_page_screenshot_returns_base64_not_path(self):
		"""Page.screenshot returns base64 str; Playwright's path=/full_page= kwargs do not exist."""
		params = inspect.signature(Page.screenshot).parameters
		assert 'path' not in params, 'Page.screenshot grew a path= kwarg; revisit call sites'
		sig = inspect.signature(Page.screenshot)
		assert sig.return_annotation in ('str', str)

	def test_playwright_only_page_methods_still_absent(self):
		"""If browser-use ever adds these, the compat layer can be simplified — flag it."""
		playwright_only = ['locator', 'wait_for_selector', 'wait_for_load_state', 'check', 'uncheck', 'query_selector_all']
		appeared = [name for name in playwright_only if hasattr(Page, name)]
		assert not appeared, f'browser-use Page now provides {appeared}; simplify workflow_use/compat/cdp.py'

	def test_dom_node_fields(self):
		"""Element finders read these fields; EnhancedDOMTreeNode is slotted so typos = dead code."""
		fields = set(EnhancedDOMTreeNode.__dataclass_fields__.keys())
		required = {'node_value', 'attributes', 'ax_node', 'is_visible', 'children_nodes'}
		missing = required - fields
		assert not missing, f'EnhancedDOMTreeNode lost fields the element finder reads: {missing}'
		# tag_name/xpath are properties, not dataclass fields
		for prop in ('tag_name', 'xpath'):
			assert hasattr(EnhancedDOMTreeNode, prop), f'EnhancedDOMTreeNode.{prop} disappeared'
		assert hasattr(EnhancedDOMTreeNode, 'get_all_children_text'), 'text extraction depends on get_all_children_text()'

	def test_dom_node_has_no_flat_text_attributes(self):
		"""Guard against regressing to getattr(node, 'text'/'aria_label'/...) which silently returns ''."""
		fields = set(EnhancedDOMTreeNode.__dataclass_fields__.keys())
		idealized = {'text', 'aria_label', 'placeholder', 'title', 'alt', 'inner_text', 'css_selector'}
		appeared = idealized & fields
		assert not appeared, f'EnhancedDOMTreeNode now has {appeared}; element finder fallbacks can be simplified'

	def test_llm_completion_field(self):
		"""LLM responses expose .completion (not LangChain's .content)."""
		fields = set(ChatInvokeCompletion.model_fields.keys())
		assert 'completion' in fields, 'ChatInvokeCompletion.completion disappeared'
		assert 'content' not in fields, 'ChatInvokeCompletion grew .content; audit call sites reading it'

	def test_builtin_action_names(self):
		"""Actions the engine constructs/excludes by name must exist in the registry."""
		registry_names = set(Tools().registry.registry.actions.keys())
		relied_upon = {'go_back', 'click', 'input', 'scroll', 'navigate', 'send_keys', 'upload_file', 'extract'}
		missing = relied_upon - registry_names
		assert not missing, f'browser-use registry lost actions: {missing} (have: {sorted(registry_names)})'

	def test_go_forward_still_not_builtin(self):
		"""GoForwardStep needs the custom controller action while browser-use lacks a builtin."""
		registry_names = set(Tools().registry.registry.actions.keys())
		assert 'go_forward' not in registry_names, (
			'browser-use now ships go_forward; the custom controller action can delegate to it'
		)


# --- Static scan -------------------------------------------------------------------

# Playwright-only patterns that raise AttributeError/TypeError on the CDP actor surface.
FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
	(r'\.locator\(', 'Page.locator does not exist on the CDP actor Page'),
	(r'\bpage\.wait_for_selector\(', 'Page.wait_for_selector does not exist'),
	(r'\.wait_for_load_state\(', 'Page.wait_for_load_state does not exist'),
	(r'\bpage\.check\(', 'Page.check does not exist (use Element.check)'),
	(r'\bpage\.uncheck\(', 'Page.uncheck does not exist (use compat set_checkbox_state)'),
	(r'\.query_selector_all\(', 'query_selector_all does not exist (use get_elements_by_css_selector)'),
	(r'(?<!asyncio)\.wait_for\(', 'Locator.wait_for does not exist (use compat wait_for_element)'),
	(r'select_option\(\s*label=', 'Element.select_option takes values only, no label='),
	(r'\.click\(\s*force=', 'Element.click takes no force= kwarg'),
	(r'\.is_visible\(\)', 'ElementHandle.is_visible does not exist on CDP Element'),
	(r'\.text_content\(\)', 'ElementHandle.text_content does not exist on CDP Element'),
	(r'\.inner_text\(\)', 'ElementHandle.inner_text does not exist on CDP Element'),
	(r'screenshot\(\s*path=', 'Page.screenshot returns base64; it takes no path= kwarg'),
]

# The compatibility layer is the single place allowed to know about surface differences.
SCAN_EXEMPT = {'compat/cdp.py'}


def iter_engine_files():
	for path in sorted(WORKFLOW_USE_ROOT.rglob('*.py')):
		rel = path.relative_to(WORKFLOW_USE_ROOT).as_posix()
		if rel in SCAN_EXEMPT or '/tests/' in f'/{rel}':
			continue
		yield rel, path


class TestNoPlaywrightIsms:
	"""The engine must not call Playwright-only APIs outside workflow_use/compat/cdp.py."""

	def test_no_playwright_calls_in_engine(self):
		violations: list[str] = []
		for rel, path in iter_engine_files():
			text = path.read_text(encoding='utf-8')
			for lineno, line in enumerate(text.splitlines(), start=1):
				stripped = line.strip()
				if stripped.startswith('#'):
					continue
				for pattern, why in FORBIDDEN_PATTERNS:
					if re.search(pattern, line):
						violations.append(f'{rel}:{lineno}: {stripped[:90]}  <-- {why}')
		assert not violations, 'Playwright-only API calls found (each raises at runtime on browser-use CDP):\n' + '\n'.join(
			violations
		)
