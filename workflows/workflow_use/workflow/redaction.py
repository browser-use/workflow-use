"""Log/report redaction for sensitive step values.

Recorded workflows can carry credentials and PII in step values (login flows,
card forms). Whatever the capture side does, the replay side must not re-leak
them through INFO logs or error reports.
"""

import re

# Field hints that mark a value as sensitive for logging/error-report purposes
_SENSITIVE_HINT_RE = re.compile(
	r'(password|passwd|pwd|otp\b|one.?time|verification|security.?code|cvv|cvc|card.?number|kart|ssn\b|social.?security|tckn|kimlik|iban|secret|token)',
	re.IGNORECASE,
)
VALUE_MASK = '********'


def redact_step_value(step, value):
	"""Mask a step value in logs/error reports when the field looks sensitive.

	*step* may be a workflow step or an action params object - any attribute bag
	with target_text/description/cssSelector-style fields.
	"""
	if value is None:
		return None
	text = str(value)
	if text == VALUE_MASK:
		return text
	hints = ' '.join(
		str(getattr(step, field, '') or '') for field in ('target_text', 'targetText', 'description', 'cssSelector', 'xpath')
	)
	return VALUE_MASK if _SENSITIVE_HINT_RE.search(hints) else text
