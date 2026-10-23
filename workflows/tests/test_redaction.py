"""Tests for sensitive-value redaction and sensitive-type default omission.

Run with: ``uv run pytest tests/test_redaction.py``
"""

from types import SimpleNamespace

from workflow_use.workflow.redaction import VALUE_MASK, redact_step_value
from workflow_use.workflow.variable_identifier import (
	SENSITIVE_VARIABLE_TYPES,
	VariableCandidate,
	VariableIdentifier,
	VariableType,
)


def step(**fields):
	return SimpleNamespace(**fields)


class TestRedactStepValue:
	def test_password_hint_masks(self):
		assert redact_step_value(step(target_text='Password'), 'redactable-value') == VALUE_MASK

	def test_mobile_field_masks(self):
		"""Free-text phone inputs are commonly named mobile/cell, not type=tel."""
		assert redact_step_value(step(target_text='Mobile number'), '5551234567') == VALUE_MASK

	def test_cell_phone_field_masks(self):
		assert redact_step_value(step(cssSelector='input[name="cellPhone"]'), '5551234567') == VALUE_MASK

	def test_turkish_cep_field_masks(self):
		assert redact_step_value(step(target_text='Cep numarası'), '5551234567') == VALUE_MASK

	def test_recep_name_is_not_cep(self):
		"""\\bcep\\b must not fire inside names like Recep."""
		assert redact_step_value(step(target_text='Recep Bey'), 'merhaba') == 'merhaba'

	def test_phone_type_hint_masks(self):
		assert redact_step_value(step(inputType='tel', target_text='Contact'), '5551234567') == VALUE_MASK

	def test_turkish_phone_label_masks(self):
		assert redact_step_value(step(target_text='Cep Telefon Numarası'), '5551234567') == VALUE_MASK

	def test_cc_autocomplete_selector_masks(self):
		assert redact_step_value(step(cssSelector='input[autocomplete="cc-number"]'), '4111111111111111') == VALUE_MASK

	def test_element_text_hint_masks(self):
		"""Legacy steps may only carry the hint in elementText."""
		assert redact_step_value(step(elementText='One-time verification code'), '123456') == VALUE_MASK

	def test_plain_field_untouched(self):
		assert redact_step_value(step(target_text='Search term'), 'red shoes') == 'red shoes'

	def test_hotel_is_not_tel(self):
		assert redact_step_value(step(target_text='Hotel name'), 'Grand Hotel') == 'Grand Hotel'

	def test_masked_stays_masked(self):
		assert redact_step_value(step(), VALUE_MASK) == VALUE_MASK


class TestSensitiveDefaults:
	def _schema_entry(self, variable_type, value, confidence, suggested_default, name='v', context=None, required=True):
		identifier = VariableIdentifier()
		candidate = VariableCandidate(
			value=value,
			variable_name=name,
			variable_type=variable_type,
			confidence=confidence,
			context=context or {},
			suggested_default=suggested_default,
			required=required,
		)
		return identifier._generate_input_schema({name: candidate})[0]

	def test_context_detected_password_gets_no_default(self):
		"""A 0.85-confidence password (context-detected) is still a secret."""
		# The value is an inert placeholder, kept deliberately un-password-like
		# so secret scanners don't flag the fixture itself.
		entry = self._schema_entry(VariableType.PASSWORD, 'example-value-1', 0.85, 'example-value-1')
		assert 'default' not in entry

	def test_phone_gets_no_default(self):
		entry = self._schema_entry(VariableType.PHONE, '5551234567', 0.9, '5551234567')
		assert 'default' not in entry

	def test_masked_password_gets_no_default_either(self):
		"""Even a masked capture must not become a default: defaults are typed
		verbatim on replay, so '********' would literally enter 8 asterisks."""
		entry = self._schema_entry(VariableType.PASSWORD, '********', 0.85, '********')
		assert 'default' not in entry

	def test_sensitive_forces_required(self):
		"""With no default allowed, the value must come from the caller."""
		entry = self._schema_entry(VariableType.PASSWORD, '********', 0.85, None, required=False)
		assert entry['required'] is True

	def test_string_typed_password_name_gets_no_default(self):
		"""A field NAMED like a credential is sensitive even when pattern
		matching classified its value as plain STRING."""
		entry = self._schema_entry(VariableType.STRING, 'example-value-2', 0.7, 'example-value-2', name='user_password')
		assert 'default' not in entry
		assert entry['required'] is True

	def test_string_typed_iban_context_gets_no_default(self):
		entry = self._schema_entry(
			VariableType.STRING, 'TR000000000000000000000000', 0.7, None, context={'label': 'IBAN'}
		)
		assert 'default' not in entry

	def test_plain_string_keeps_default(self):
		entry = self._schema_entry(VariableType.STRING, 'red shoes', 0.7, 'red shoes')
		assert entry.get('default') == 'red shoes'

	def test_sensitive_set_covers_expected_types(self):
		assert {VariableType.PASSWORD, VariableType.CREDIT_CARD, VariableType.SSN} <= SENSITIVE_VARIABLE_TYPES
