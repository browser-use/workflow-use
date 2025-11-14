"""
Configuration for Variable Identification

This module provides configuration options for customizing how variables
are identified in workflow automation.
"""

from dataclasses import dataclass, field
from typing import Dict, Set


@dataclass
class VariableIdentificationConfig:
	"""Configuration for variable identification behavior."""

	# Confidence threshold (0.0 to 1.0)
	# Values with confidence below this won't be parameterized
	min_confidence: float = 0.6

	# Enable LLM-based identification for ambiguous cases
	use_llm: bool = False

	# Patterns to always parameterize (case-insensitive)
	always_parameterize: Set[str] = field(
		default_factory=lambda: {
			'email',
			'password',
			'username',
			'phone',
			'ssn',
			'social_security',
			'credit_card',
			'card_number',
			'cvv',
			'routing',
			'account',
		}
	)

	# Patterns to never parameterize (static values)
	never_parameterize: Set[str] = field(
		default_factory=lambda: {
			'submit',
			'cancel',
			'ok',
			'yes',
			'no',
			'true',
			'false',
			'search',
			'login',
			'signup',
			'signin',
		}
	)

	# Custom regex patterns for domain-specific fields
	# Format: {field_name_pattern: variable_type}
	custom_patterns: Dict[str, str] = field(default_factory=dict)

	# Minimum value length to consider for parameterization
	min_value_length: int = 2

	# Maximum value length (very long values might not be variables)
	max_value_length: int = 500

	# Whether to use context hints (labels, placeholders) for detection
	use_context_hints: bool = True

	# Whether to generate default values in schema
	include_defaults: bool = True

	# Whether to mark all identified variables as required
	mark_as_required: bool = True

	# Custom variable name mappings
	# Format: {detected_name: preferred_name}
	variable_name_mappings: Dict[str, str] = field(
		default_factory=lambda: {
			'fname': 'first_name',
			'lname': 'last_name',
			'tel': 'phone_number',
			'mob': 'mobile_number',
			'dob': 'date_of_birth',
		}
	)

	# Field name patterns that should be grouped
	# (e.g., firstName, middleName, lastName → name_first, name_middle, name_last)
	group_related_fields: bool = True

	# Domain-specific configurations
	domain_config: Dict[str, any] = field(default_factory=dict)


# Preset configurations for different use cases
class VariableConfigPresets:
	"""Preset configurations for common use cases."""

	@staticmethod
	def strict() -> VariableIdentificationConfig:
		"""
		Strict configuration - only parameterize high-confidence matches.
		Use for workflows where false positives are costly.
		"""
		return VariableIdentificationConfig(
			min_confidence=0.85,
			use_llm=False,
			use_context_hints=True,
			mark_as_required=True,
			include_defaults=False,
		)

	@staticmethod
	def balanced() -> VariableIdentificationConfig:
		"""
		Balanced configuration - reasonable confidence threshold.
		Default recommended setting.
		"""
		return VariableIdentificationConfig(
			min_confidence=0.6,
			use_llm=False,
			use_context_hints=True,
			mark_as_required=True,
			include_defaults=True,
		)

	@staticmethod
	def aggressive() -> VariableIdentificationConfig:
		"""
		Aggressive configuration - parameterize more values.
		Use when you want maximum flexibility in workflows.
		"""
		return VariableIdentificationConfig(
			min_confidence=0.4,
			use_llm=False,
			use_context_hints=True,
			mark_as_required=False,
			include_defaults=True,
		)

	@staticmethod
	def ai_assisted() -> VariableIdentificationConfig:
		"""
		AI-assisted configuration - use LLM for ambiguous cases.
		Best accuracy but requires LLM access.
		"""
		return VariableIdentificationConfig(
			min_confidence=0.5,
			use_llm=True,
			use_context_hints=True,
			mark_as_required=True,
			include_defaults=True,
		)

	@staticmethod
	def form_filling() -> VariableIdentificationConfig:
		"""
		Optimized for form-filling workflows.
		Recognizes common form fields and patterns.
		"""
		config = VariableIdentificationConfig(
			min_confidence=0.65,
			use_context_hints=True,
			mark_as_required=True,
			include_defaults=True,
		)

		# Add common form field patterns
		config.always_parameterize.update(
			{
				'address',
				'city',
				'state',
				'zip',
				'postal',
				'country',
				'firstname',
				'lastname',
				'middlename',
				'dateofbirth',
				'gender',
				'company',
				'occupation',
			}
		)

		return config

	@staticmethod
	def ecommerce() -> VariableIdentificationConfig:
		"""
		Optimized for e-commerce workflows.
		Handles product searches, checkouts, etc.
		"""
		config = VariableIdentificationConfig(
			min_confidence=0.6,
			use_context_hints=True,
			mark_as_required=False,  # Many fields optional in e-commerce
			include_defaults=True,
		)

		config.always_parameterize.update(
			{
				'product',
				'quantity',
				'size',
				'color',
				'shipping',
				'billing',
				'coupon',
				'promo',
			}
		)

		return config


# Global configuration instance
_global_config = VariableIdentificationConfig()


def get_config() -> VariableIdentificationConfig:
	"""Get the global configuration instance."""
	return _global_config


def set_config(config: VariableIdentificationConfig) -> None:
	"""Set the global configuration instance."""
	global _global_config
	_global_config = config


def load_preset(preset_name: str) -> None:
	"""
	Load a preset configuration.

	Args:
		preset_name: One of 'strict', 'balanced', 'aggressive', 'ai_assisted',
					 'form_filling', 'ecommerce'
	"""
	presets = {
		'strict': VariableConfigPresets.strict,
		'balanced': VariableConfigPresets.balanced,
		'aggressive': VariableConfigPresets.aggressive,
		'ai_assisted': VariableConfigPresets.ai_assisted,
		'form_filling': VariableConfigPresets.form_filling,
		'ecommerce': VariableConfigPresets.ecommerce,
	}

	if preset_name not in presets:
		raise ValueError(f"Unknown preset '{preset_name}'. Available: {list(presets.keys())}")

	set_config(presets[preset_name]())
