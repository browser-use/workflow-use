"""CDP compatibility layer for browser-use's actor API.

The replay engine was originally written against Playwright's Page/Locator API.
browser-use >= 0.2 exposes a CDP-based actor surface instead: no ``page.locator``,
``wait_for_selector``, ``wait_for_load_state``, ``page.check``/``uncheck``,
``query_selector_all``; ``evaluate`` requires arrow-function source and returns a
*string* (objects/arrays JSON-stringified, booleans as ``'True'``/``'False'``);
``screenshot`` returns base64 instead of writing to a path.

This module is the single place that knows those differences. Engine code imports
the primitives below; ``tests/test_browser_use_contract.py`` statically enforces
that no Playwright-only call exists outside this file.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import secrets
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
	from browser_use.actor.element import Element
	from browser_use.actor.page import Page

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_S = 0.1

_VISIBILITY_JS = (
	'() => { const r = this.getBoundingClientRect(); const s = getComputedStyle(this); '
	"return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; }"
)


def parse_js_result(raw: str | None) -> Any:
	"""Decode the string returned by Page.evaluate / Element.evaluate.

	browser-use stringifies every result: ``None`` -> ``''``, JS strings pass
	through raw, dict/list are JSON-encoded, numbers/booleans go through
	``str()`` (so JS ``true`` arrives as ``'True'``).
	"""
	if raw is None or raw == '':
		return None
	if raw == 'True':
		return True
	if raw == 'False':
		return False
	try:
		return json.loads(raw)
	except (ValueError, TypeError):
		return raw


async def evaluate(page_or_element: 'Page | Element', page_function: str, *args: Any) -> Any:
	"""Run JS through the actor API and return a decoded Python value."""
	raw = await page_or_element.evaluate(page_function, *args)
	return parse_js_result(raw)


async def element_is_visible(element: 'Element') -> bool:
	"""Playwright ``is_visible()`` equivalent (geometry + computed style)."""
	try:
		return await evaluate(element, _VISIBILITY_JS) is True
	except Exception:
		return False


async def element_text_content(element: 'Element') -> str:
	"""Playwright ``text_content()`` equivalent."""
	try:
		return str(await element.evaluate('() => this.textContent || ""'))
	except Exception:
		return ''


async def query_selector_all(page: 'Page', selector: str) -> list['Element']:
	"""Playwright ``query_selector_all`` equivalent; [] on invalid selector."""
	try:
		return await page.get_elements_by_css_selector(selector)
	except Exception as e:
		logger.debug(f'query_selector_all({selector!r}) failed: {e}')
		return []


async def wait_for_element(
	page: 'Page',
	selector: str,
	timeout_ms: float = 2000,
	state: str = 'visible',
	poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
) -> 'Element | None':
	"""Playwright ``wait_for_selector`` equivalent.

	Polls until an element matching *selector* is attached (``state='attached'``)
	or visible (``state='visible'``). Returns the element, or None on timeout —
	callers decide whether that is an error.
	"""
	deadline = asyncio.get_event_loop().time() + max(timeout_ms, 0) / 1000
	while True:
		elements = await query_selector_all(page, selector)
		for element in elements:
			if state != 'visible' or await element_is_visible(element):
				return element
		if asyncio.get_event_loop().time() >= deadline:
			return None
		await asyncio.sleep(poll_interval_s)


_MARKER_ATTR = 'data-workflow-use-match'

_XPATH_MARK_JS = """(xpath, marker, token) => {
	try {
		const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
		const node = result.singleNodeValue;
		if (node && node.nodeType === Node.ELEMENT_NODE) {
			node.setAttribute(marker, token);
			return true;
		}
	} catch (e) {}
	return false;
}"""


async def _fetch_marked_element(page: 'Page', token: str) -> 'Element | None':
	"""Fetch the element tagged with our per-lookup token and untag it."""
	elements = await query_selector_all(page, f'[{_MARKER_ATTR}="{token}"]')
	if not elements:
		return None
	element = elements[0]
	try:
		await element.evaluate(f"() => this.removeAttribute('{_MARKER_ATTR}')")
	except Exception:
		pass
	return element


async def get_element_by_xpath(page: 'Page', xpath: str, timeout_ms: float = 2000) -> 'Element | None':
	"""Resolve an XPath to an Element handle.

	The CDP actor API only queries by CSS, so the matched node is tagged with a
	temporary attribute, fetched by CSS, then untagged. The marker value is a
	per-lookup token so overlapping lookups can't select each other's element.
	"""
	deadline = asyncio.get_event_loop().time() + max(timeout_ms, 0) / 1000
	while True:
		token = secrets.token_hex(6)
		try:
			found = await evaluate(page, _XPATH_MARK_JS, xpath, _MARKER_ATTR, token)
			if found is True:
				element = await _fetch_marked_element(page, token)
				if element is not None and await element_is_visible(element):
					return element
		except Exception as e:
			logger.debug(f'get_element_by_xpath({xpath!r}) failed: {e}')
		if asyncio.get_event_loop().time() >= deadline:
			return None
		await asyncio.sleep(DEFAULT_POLL_INTERVAL_S)


_TEXT_MATCH_MARK_JS = """(tag, wanted, marker, token) => {
	const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
	const target = norm(wanted);
	if (!target) return false;
	let candidates;
	try { candidates = document.querySelectorAll(tag); } catch (e) { return false; }
	for (const el of candidates) {
		const rect = el.getBoundingClientRect();
		const style = getComputedStyle(el);
		const visible = rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
		if (!visible) continue;
		const haystacks = [
			el.innerText,
			el.getAttribute('aria-label'),
			el.getAttribute('title'),
			el.getAttribute('placeholder'),
			el.value,
		];
		if (haystacks.some((h) => norm(h).includes(target))) {
			el.setAttribute(marker, token);
			return true;
		}
	}
	return false;
}"""


async def find_element_by_text(page: 'Page', tag: str, text: str, timeout_ms: float = 2000) -> 'Element | None':
	"""Find a visible *tag* element whose rendered text or accessible attributes contain *text*.

	One page-side pass over ALL candidates (rendered ``innerText`` - not hidden
	``textContent`` - plus aria-label/title/placeholder/value), polled until the
	deadline so late-rendering elements are still found.
	"""
	deadline = asyncio.get_event_loop().time() + max(timeout_ms, 0) / 1000
	while True:
		token = secrets.token_hex(6)
		try:
			found = await evaluate(page, _TEXT_MATCH_MARK_JS, tag, text, _MARKER_ATTR, token)
			if found is True:
				element = await _fetch_marked_element(page, token)
				if element is not None:
					return element
		except Exception as e:
			logger.debug(f'find_element_by_text({tag!r}, {text!r}) failed: {e}')
		if asyncio.get_event_loop().time() >= deadline:
			return None
		await asyncio.sleep(DEFAULT_POLL_INTERVAL_S)


async def wait_for_load_state(page: 'Page', state: str = 'load', timeout_ms: float = 10000) -> bool:
	"""Approximate Playwright ``wait_for_load_state`` on the CDP surface.

	Polls ``document.readyState``. ``'networkidle'`` additionally requires the
	ready state to hold for a short settle window (the actor API exposes no
	network-inflight signal). Returns False on timeout instead of raising.
	"""
	target_states = ('interactive', 'complete') if state == 'domcontentloaded' else ('complete',)
	settle_s = 0.5 if state == 'networkidle' else 0.0
	deadline = asyncio.get_event_loop().time() + max(timeout_ms, 0) / 1000
	settled_since: float | None = None
	while True:
		try:
			ready = await evaluate(page, '() => document.readyState')
		except Exception:
			ready = None  # mid-navigation; keep polling
		now = asyncio.get_event_loop().time()
		if ready in target_states:
			if settle_s == 0.0:
				return True
			if settled_since is None:
				settled_since = now
			elif now - settled_since >= settle_s:
				return True
		else:
			settled_since = None
		if now >= deadline:
			return False
		await asyncio.sleep(DEFAULT_POLL_INTERVAL_S)


async def screenshot_to_file(page: 'Page', path: str, format: str = 'png') -> None:
	"""Playwright ``screenshot(path=...)`` equivalent: decode base64 and write."""
	data = await page.screenshot(format=format)
	raw = base64.b64decode(data)
	await asyncio.to_thread(Path(path).write_bytes, raw)


async def is_checked(element: 'Element') -> bool:
	return await evaluate(element, '() => !!this.checked') is True


async def set_checkbox_state(element: 'Element', checked: bool) -> bool:
	"""Playwright ``check()``/``uncheck()`` equivalent via user-like clicks.

	Returns True when the element ends up in the desired state.
	"""
	current = await is_checked(element)
	if current == checked:
		return True
	await element.click()
	return await is_checked(element) == checked


async def is_select_element(element: 'Element') -> bool:
	return await evaluate(element, "() => this.tagName === 'SELECT'") is True


_SELECT_BY_TEXT_JS = """(wanted) => {
	if (this.tagName !== 'SELECT') return 'not-select';
	const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
	const target = norm(wanted);
	const options = Array.from(this.options);
	let index = options.findIndex((o) => norm(o.label) === target || norm(o.textContent) === target);
	if (index === -1) index = options.findIndex((o) => norm(o.value) === target);
	if (index === -1) return 'no-match';
	if (this.selectedIndex !== index) {
		this.selectedIndex = index;
		this.dispatchEvent(new Event('input', { bubbles: true }));
		this.dispatchEvent(new Event('change', { bubbles: true }));
	}
	return 'ok';
}"""


async def select_option_by_text(element: 'Element', text: str) -> bool:
	"""Select a ``<select>`` option by visible label (fallback: value attribute).

	``Element.select_option`` matches option *values* and cannot see option label
	text (element-node nodeValue is empty at depth 1), so visible-text selection
	is implemented in page JS with proper input/change events.
	"""
	result = await evaluate(element, _SELECT_BY_TEXT_JS, text)
	if result == 'ok':
		return True
	logger.debug(f'select_option_by_text({text!r}) -> {result}')
	return False


async def press_key_on_element(page: 'Page', element: 'Element', key: str) -> None:
	"""Playwright ``locator.press`` equivalent: focus the element, press on page."""
	await element.focus()
	await page.press(key)
