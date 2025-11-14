"""
AI-Powered Variable Identifier for Workflow Automation

This module provides intelligent identification of input values that should be
parameterized as variables in workflow definitions. It uses pattern matching,
heuristics, and optional LLM assistance to create deterministic, reusable workflows.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class VariableType(str, Enum):
	"""Types of variables that can be identified."""

	STRING = 'string'
	EMAIL = 'email'
	PHONE = 'phone'
	NUMBER = 'number'
	BOOLEAN = 'boolean'
	URL = 'url'
	DATE = 'date'
	CREDIT_CARD = 'credit_card'
	SSN = 'ssn'
	ZIP_CODE = 'zip_code'
	PASSWORD = 'password'


@dataclass
class VariableCandidate:
	"""A candidate value that could be parameterized as a variable."""

	value: str
	variable_name: str
	variable_type: VariableType
	confidence: float  # 0.0 to 1.0
	context: Dict[str, Any]  # Context from the step (label, placeholder, etc.)
	suggested_default: Optional[str] = None
	description: Optional[str] = None
	required: bool = True


class VariableIdentifier:
	"""
	Identifies input values that should be parameterized as variables.

	Uses a multi-stage approach:
	1. Pattern-based detection (deterministic)
	2. Context-based detection (semantic analysis)
	3. Type inference and validation
	4. Variable name generation
	"""

	# Regex patterns for common data types
	PATTERNS = {
		VariableType.EMAIL: r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
		VariableType.PHONE: r'^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$',
		VariableType.URL: r'^https?://[^\s]+$',
		VariableType.ZIP_CODE: r'^\d{5}(-\d{4})?$',
		VariableType.SSN: r'^\d{3}-?\d{2}-?\d{4}$',
		VariableType.CREDIT_CARD: r'^\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}$',
		VariableType.DATE: r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$|^\d{4}[/-]\d{1,2}[/-]\d{1,2}$',
		VariableType.NUMBER: r'^\d+(\.\d+)?$',
	}

	# Keywords that suggest a field should be a variable
	VARIABLE_KEYWORDS = {
		'email': VariableType.EMAIL,
		'phone': VariableType.PHONE,
		'telephone': VariableType.PHONE,
		'mobile': VariableType.PHONE,
		'url': VariableType.URL,
		'website': VariableType.URL,
		'address': VariableType.STRING,
		'name': VariableType.STRING,
		'firstname': VariableType.STRING,
		'first_name': VariableType.STRING,
		'lastname': VariableType.STRING,
		'last_name': VariableType.STRING,
		'username': VariableType.STRING,
		'password': VariableType.PASSWORD,
		'ssn': VariableType.SSN,
		'social': VariableType.SSN,
		'security': VariableType.SSN,
		'zip': VariableType.ZIP_CODE,
		'postal': VariableType.ZIP_CODE,
		'card': VariableType.CREDIT_CARD,
		'credit': VariableType.CREDIT_CARD,
		'date': VariableType.DATE,
		'dob': VariableType.DATE,
		'birth': VariableType.DATE,
		'age': VariableType.NUMBER,
		'amount': VariableType.NUMBER,
		'quantity': VariableType.NUMBER,
		'price': VariableType.NUMBER,
	}

	# Values that should NOT be parameterized (common static values)
	STATIC_VALUES = {
		'',
		' ',
		'true',
		'false',
		'yes',
		'no',
		'on',
		'off',
		'1',
		'0',
		'submit',
		'cancel',
		'ok',
	}

	def __init__(self, min_confidence: float = 0.6, use_llm: bool = False):
		"""
		Initialize the variable identifier.

		Args:
			min_confidence: Minimum confidence score (0-1) to accept a variable candidate
			use_llm: Whether to use LLM for ambiguous cases (future enhancement)
		"""
		self.min_confidence = min_confidence
		self.use_llm = use_llm
		self._seen_variables: Set[str] = set()  # Track to avoid duplicates

	def identify_variables_in_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
		"""
		Analyze a workflow and identify variables in input steps.

		Args:
			workflow_data: The workflow dictionary

		Returns:
			Modified workflow with identified variables replaced with placeholders
		"""
		workflow = workflow_data.copy()
		identified_vars: Dict[str, VariableCandidate] = {}

		# Process each step
		if 'steps' in workflow:
			for i, step in enumerate(workflow['steps']):
				if step.get('type') == 'input' and 'value' in step:
					value = step['value']

					# Skip if already a variable placeholder
					if self._is_variable_placeholder(value):
						continue

					# Extract context from the step
					context = self._extract_step_context(step)

					# Identify if this should be a variable
					candidate = self.identify_variable(value, context)

					if candidate and candidate.confidence >= self.min_confidence:
						var_name = self._ensure_unique_variable_name(candidate.variable_name)
						candidate.variable_name = var_name

						# Replace value with placeholder
						workflow['steps'][i]['value'] = f'{{{var_name}}}'

						# Store the candidate
						identified_vars[var_name] = candidate

						logger.info(
							f"Identified variable '{var_name}' (type: {candidate.variable_type}, "
							f'confidence: {candidate.confidence:.2f}) in step {i}'
						)

		# Generate input schema
		if identified_vars:
			workflow['input_schema'] = self._generate_input_schema(identified_vars)

		# Add metadata about variable identification
		if 'metadata' not in workflow:
			workflow['metadata'] = {}
		workflow['metadata']['variables_auto_identified'] = True
		workflow['metadata']['identified_variable_count'] = len(identified_vars)

		return workflow

	def identify_variable(self, value: str, context: Dict[str, Any]) -> Optional[VariableCandidate]:
		"""
		Identify if a value should be a variable.

		Args:
			value: The input value to analyze
			context: Context information (labels, placeholders, field names, etc.)

		Returns:
			VariableCandidate if the value should be parameterized, None otherwise
		"""
		# Skip empty or very short values
		if not value or len(value.strip()) < 2:
			return None

		# Skip common static values
		if value.lower().strip() in self.STATIC_VALUES:
			return None

		# Stage 1: Pattern-based detection (high confidence)
		pattern_result = self._detect_by_pattern(value)
		if pattern_result:
			var_type, confidence = pattern_result
			var_name = self._generate_variable_name(var_type, context)
			return VariableCandidate(
				value=value,
				variable_name=var_name,
				variable_type=var_type,
				confidence=confidence,
				context=context,
				suggested_default=value if confidence < 0.95 else None,
				description=self._generate_description(var_name, var_type, context),
				required=True,
			)

		# Stage 2: Context-based detection (medium confidence)
		context_result = self._detect_by_context(value, context)
		if context_result:
			var_type, confidence, var_name = context_result
			return VariableCandidate(
				value=value,
				variable_name=var_name,
				variable_type=var_type,
				confidence=confidence,
				context=context,
				suggested_default=value,
				description=self._generate_description(var_name, var_type, context),
				required=True,
			)

		# Stage 3: Heuristic detection (lower confidence)
		# If the value looks dynamic (contains mixed case, numbers, special chars)
		if self._looks_dynamic(value):
			var_name = self._generate_variable_name(VariableType.STRING, context)
			return VariableCandidate(
				value=value,
				variable_name=var_name,
				variable_type=VariableType.STRING,
				confidence=0.5,  # Lower confidence
				context=context,
				suggested_default=value,
				description=self._generate_description(var_name, VariableType.STRING, context),
				required=True,
			)

		return None

	def _detect_by_pattern(self, value: str) -> Optional[Tuple[VariableType, float]]:
		"""Detect variable type by regex pattern matching."""
		for var_type, pattern in self.PATTERNS.items():
			if re.match(pattern, value.strip()):
				confidence = 0.95  # High confidence for pattern matches
				logger.debug(f"Pattern match: '{value}' detected as {var_type}")
				return (var_type, confidence)
		return None

	def _detect_by_context(self, value: str, context: Dict[str, Any]) -> Optional[Tuple[VariableType, float, str]]:
		"""Detect variable type by analyzing context (labels, placeholders, etc.)."""
		# Extract text hints from context
		hints = []
		if 'target_text' in context:
			hints.append(context['target_text'].lower())
		if 'placeholder' in context:
			hints.append(context['placeholder'].lower())
		if 'label' in context:
			hints.append(context['label'].lower())
		if 'name' in context:
			hints.append(context['name'].lower())
		if 'id' in context:
			hints.append(context['id'].lower())
		if 'description' in context:
			hints.append(context['description'].lower())

		combined_hints = ' '.join(hints)

		# Match keywords
		for keyword, var_type in self.VARIABLE_KEYWORDS.items():
			if keyword in combined_hints:
				# Generate variable name from context (with type-based fallback)
				var_name = self._generate_variable_name(var_type, context)
				confidence = 0.85  # Good confidence for context matches
				logger.debug(f"Context match: keyword '{keyword}' → {var_type} (name: {var_name})")
				return (var_type, confidence, var_name)

		# Additional check for common field patterns (even without exact keyword match)
		# This helps catch "First Name" → first_name, "Last Name" → last_name
		if combined_hints:
			# Check if hints suggest this is a name field
			if any(term in combined_hints for term in ['name', 'full name', 'given name', 'surname', 'family name']):
				# Generate variable name with fallback
				var_name = self._generate_variable_name(VariableType.STRING, context)
				if var_name and 'name' in var_name:
					confidence = 0.75  # Decent confidence for name fields
					logger.debug(f'Name field detected from context: {var_name}')
					return (VariableType.STRING, confidence, var_name)

		return None

	def _looks_dynamic(self, value: str) -> bool:
		"""
		Heuristic to determine if a value looks like dynamic user input
		rather than a static value.
		"""
		# Skip very common words
		common_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
		if value.lower() in common_words:
			return False

		# Dynamic indicators
		has_mixed_case = value != value.lower() and value != value.upper()
		has_numbers = any(c.isdigit() for c in value)
		has_special = any(c in value for c in ['@', '#', '$', '%', '&', '*', '_', '-'])
		is_long = len(value) > 10

		# If it has multiple dynamic indicators, likely a variable
		score = sum([has_mixed_case, has_numbers, has_special, is_long])
		return score >= 2

	def _generate_variable_name(self, var_type: VariableType, context: Dict[str, Any]) -> str:
		"""Generate a semantic variable name based on type and context."""
		# Try to extract from context first
		var_name = self._generate_variable_name_from_context(context, var_type)
		if var_name:
			return var_name

		# Fallback to type-based names
		type_names = {
			VariableType.EMAIL: 'email',
			VariableType.PHONE: 'phone_number',
			VariableType.URL: 'url',
			VariableType.SSN: 'social_security_number',
			VariableType.ZIP_CODE: 'zip_code',
			VariableType.CREDIT_CARD: 'credit_card_number',
			VariableType.DATE: 'date',
			VariableType.NUMBER: 'number',
			VariableType.PASSWORD: 'password',
			VariableType.STRING: 'value',
		}
		return type_names.get(var_type, 'value')

	def _generate_variable_name_from_context(self, context: Dict[str, Any], var_type: VariableType) -> str:
		"""Extract a meaningful variable name from step context."""
		# Priority: name attribute > id > label > placeholder > target_text
		for key in ['name', 'id', 'label', 'placeholder', 'target_text']:
			if key in context and context[key]:
				raw_name = context[key]
				# Clean and normalize
				var_name = self._normalize_variable_name(raw_name)
				if var_name and len(var_name) > 1:
					return var_name

		return None

	def _normalize_variable_name(self, name: str) -> str:
		"""Normalize a string to a valid variable name."""
		# Convert to lowercase
		name = name.lower()

		# Remove common prefixes/suffixes
		for prefix in ['input-', 'field-', 'txt-', 'input_', 'field_']:
			if name.startswith(prefix):
				name = name[len(prefix) :]

		# Replace special chars with underscore
		name = re.sub(r'[^a-z0-9_]', '_', name)

		# Remove multiple consecutive underscores
		name = re.sub(r'_+', '_', name)

		# Remove leading/trailing underscores
		name = name.strip('_')

		# Ensure it doesn't start with a number
		if name and name[0].isdigit():
			name = 'field_' + name

		return name

	def _ensure_unique_variable_name(self, base_name: str) -> str:
		"""Ensure variable name is unique by adding suffix if needed."""
		if base_name not in self._seen_variables:
			self._seen_variables.add(base_name)
			return base_name

		# Add numeric suffix
		counter = 2
		while f'{base_name}_{counter}' in self._seen_variables:
			counter += 1

		unique_name = f'{base_name}_{counter}'
		self._seen_variables.add(unique_name)
		return unique_name

	def _extract_step_context(self, step: Dict[str, Any]) -> Dict[str, Any]:
		"""Extract relevant context from a workflow step."""
		context = {}

		# Extract from semantic info
		if 'semanticInfo' in step:
			semantic = step['semanticInfo']
			for key in ['labelText', 'placeholder', 'ariaLabel', 'name', 'id', 'textContent']:
				if key in semantic:
					context[key.lower().replace('text', '')] = semantic[key]

		# Extract from step fields
		if 'target_text' in step:
			context['target_text'] = step['target_text']

		# IMPORTANT: Extract from description - this often contains "First Name", "Last Name", etc.
		if 'description' in step:
			context['description'] = step['description']

		# Extract from CSS selector
		if 'cssSelector' in step and step['cssSelector']:
			# Try to extract name or id from selector
			css = step['cssSelector']
			name_match = re.search(r'\[name=["\']([^"\']+)["\']\]', css)
			if name_match:
				context['name'] = name_match.group(1)
			id_match = re.search(r'\[id=["\']([^"\']+)["\']\]', css)
			if id_match:
				context['id'] = id_match.group(1)

		return context

	def _generate_description(self, var_name: str, var_type: VariableType, context: Dict[str, Any]) -> str:
		"""Generate a human-readable description for the variable."""
		# Try to use context for description
		if 'label' in context and context['label']:
			return context['label']
		if 'placeholder' in context and context['placeholder']:
			return f'Enter {context["placeholder"].lower()}'

		# Fallback to generated description
		readable_name = var_name.replace('_', ' ').title()
		return f'{readable_name} ({var_type.value})'

	def _generate_input_schema(self, variables: Dict[str, VariableCandidate]) -> List[Dict[str, Any]]:
		"""Generate input schema from identified variables."""
		# Map our detailed types to WorkflowInputSchemaDefinition types
		# Schema only supports: 'string', 'number', 'bool'
		type_mapping = {
			VariableType.STRING: 'string',
			VariableType.EMAIL: 'string',
			VariableType.PHONE: 'string',
			VariableType.URL: 'string',
			VariableType.SSN: 'string',
			VariableType.ZIP_CODE: 'string',
			VariableType.CREDIT_CARD: 'string',
			VariableType.DATE: 'string',
			VariableType.PASSWORD: 'string',
			VariableType.NUMBER: 'number',
			VariableType.BOOLEAN: 'bool',
		}

		# Format info for detailed types (used in validation/display)
		format_mapping = {
			VariableType.EMAIL: 'email',
			VariableType.PHONE: 'phone',
			VariableType.URL: 'url',
			VariableType.SSN: 'ssn',
			VariableType.ZIP_CODE: 'zip-code',
			VariableType.CREDIT_CARD: 'credit-card',
			VariableType.DATE: 'date',
			VariableType.PASSWORD: 'password',
		}

		schema = []
		for var_name, candidate in variables.items():
			# Map to schema type
			schema_type = type_mapping.get(candidate.variable_type, 'string')

			entry = {
				'name': var_name,
				'type': schema_type,
				'required': candidate.required,
			}

			# Add format if we have detailed type info
			if candidate.variable_type in format_mapping:
				entry['format'] = format_mapping[candidate.variable_type]

			# Add description
			if candidate.description:
				entry['description'] = candidate.description

			# IMPORTANT: Always add default value (original value from workflow)
			# This allows the workflow to run without user input if desired
			if candidate.suggested_default:
				entry['default'] = candidate.suggested_default
			else:
				# If no suggested default, use the original value
				entry['default'] = candidate.value

			schema.append(entry)

		return schema

	def _is_variable_placeholder(self, value: str) -> bool:
		"""Check if a value is already a variable placeholder like {variable_name}."""
		return bool(re.match(r'^\{[a-zA-Z_][a-zA-Z0-9_]*\}$', str(value)))


# Convenience function for direct usage
def identify_variables_in_workflow(
	workflow_data: Dict[str, Any], min_confidence: float = 0.6, use_llm: bool = False
) -> Dict[str, Any]:
	"""
	Identify and parameterize variables in a workflow.

	Args:
		workflow_data: The workflow dictionary
		min_confidence: Minimum confidence threshold (0-1)
		use_llm: Whether to use LLM for ambiguous cases

	Returns:
		Modified workflow with variables identified and replaced
	"""
	identifier = VariableIdentifier(min_confidence=min_confidence, use_llm=use_llm)
	return identifier.identify_variables_in_workflow(workflow_data)
