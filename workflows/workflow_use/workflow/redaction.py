"""Log/report redaction for sensitive step values.

Recorded workflows can carry credentials and PII in step values (login flows,
card forms). Whatever the capture side does, the replay side must not re-leak
them through INFO logs or error reports.
"""

import re

# Field hints that mark a value as sensitive for logging/error-report purposes.
# Covers autocomplete tokens (cc-number, one-time-code), type hints (tel) and
# EN+TR naming conventions for credentials, cards, ids and phone numbers.
_SENSITIVE_HINT_RE = re.compile(
	r'(password|passwd|pwd|otp\b|one.?time|verification|security.?code|cvv|cvc|csc\b'
	r'|card.?number|cc-number|cc-csc|cc-exp|kart|ssn\b|social.?security|tckn|kimlik|iban'
	r'|secret|token|type=.?tel\b|\btel\b|telefon|phone|gsm\b|mobile|mobil\b'
	r'|\bcell(ular)?\b|msisdn|\bcep\b)',
	re.IGNORECASE,
)
VALUE_MASK = '********'


def is_sensitive_hint(*hints) -> bool:
	"""True when any free-form hint (field name, label, id, placeholder...)
	suggests the associated value is a credential or PII."""
	joined = ' '.join(str(h) for h in hints if h)
	return bool(_SENSITIVE_HINT_RE.search(joined))

# Recorder/step fields that can reveal what kind of field the value belongs to
_HINT_FIELDS = (
	'target_text',
	'targetText',
	'description',
	'cssSelector',
	'xpath',
	'elementText',
	'elementTag',
	'inputType',
)


def redact_step_value(step, value):
	"""Mask a step value in logs/error reports when the field looks sensitive.

	*step* may be a workflow step or an action params object - any attribute bag
	with target_text/description/cssSelector-style fields. Values that arrive
	already masked stay masked.
	"""
	if value is None:
		return None
	text = str(value)
	if text == VALUE_MASK:
		return text
	hints = ' '.join(str(getattr(step, field, '') or '') for field in _HINT_FIELDS)
	return VALUE_MASK if _SENSITIVE_HINT_RE.search(hints) else text
