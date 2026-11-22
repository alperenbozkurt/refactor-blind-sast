"""Configuration validation service.

Exposes a small Flask API for validating configuration dictionaries against
named pattern validators, registered custom validators, and ad-hoc
validation expressions.
"""

import json
import re
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

PATTERN_VALIDATORS = {
    'email': '^[^@]+@[^@]+\\.[^@]+$',
    'phone': '^\\d{10}$',
    'date': '^\\d{4}-\\d{2}-\\d{2}$',
}

BUILTIN_CUSTOM_VALIDATORS = {
    'adult': 'datetime.strptime(value, "%Y-%m-%d").year <= datetime.now().year - 18',
    'strong_password': 'len(value) >= 8 and any(c.isupper() for c in value) and any(c.isdigit() for c in value)',
}

MSG_CONFIG_AND_RULES_REQUIRED = 'Config and rules required'
MSG_NAME_AND_LOGIC_REQUIRED = 'Name and logic required'
MSG_VALUE_AND_EXPRESSION_REQUIRED = 'Value and expression required'
MSG_ADD_VALIDATOR_FAILED = 'Failed to add validator'
MSG_VALIDATOR_ADDED = 'Validator added'

MSG_MISSING_FIELD = 'Missing required field'
MSG_INVALID_RULE = 'Invalid validation rule'


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_eval_environment(value):
    """Build the restricted global namespace used for inline expressions."""
    return {'value': value, 're': re, 'datetime': datetime}


def _extract_payload(required_fields, missing_message):
    """Return ``(payload, error_response)`` for the current JSON request.

    ``error_response`` is ``None`` when the payload is present and contains
    every required field.
    """
    data = request.get_json()
    if not data or any(field not in data for field in required_fields):
        return None, (jsonify({'error': missing_message}), HTTP_BAD_REQUEST)
    return data, None


# ---------------------------------------------------------------------------
# Validation engine
# ---------------------------------------------------------------------------

class ConfigValidator:
    """Validates configuration values against named or inline rules."""

    def __init__(self):
        self.validators = dict(PATTERN_VALIDATORS)
        self.custom_validators = {}

    def add_custom_validator(self, name, validation_logic):
        try:
            compiled_logic = eval(f'lambda value: {validation_logic}')
            self.custom_validators[name] = compiled_logic
            return True
        except Exception as e:
            print(f'Validator compilation failed: {str(e)}')
            return False

    def validate(self, config, rules):
        errors = {}
        for (field, rule) in rules.items():
            error = self._validate_field(field, config.get(field), rule)
            if error is not None:
                errors[field] = error
        return errors if errors else None

    # -- internal helpers ---------------------------------------------------

    def _validate_field(self, field, value, rule):
        """Return the error message for a single field, or ``None`` if valid."""
        if value is None:
            return MSG_MISSING_FIELD
        if isinstance(rule, str):
            return self._validate_named_rule(field, value, rule)
        if isinstance(rule, dict):
            return self._validate_dict_rule(field, value, rule)
        return MSG_INVALID_RULE

    def _validate_named_rule(self, field, value, rule):
        if rule in self.validators:
            return self._validate_pattern(rule, value)
        if rule in self.custom_validators:
            return self._validate_custom(field, value, rule)
        return f'Unknown validator: {rule}'

    def _validate_pattern(self, rule, value):
        if not re.match(self.validators[rule], str(value)):
            return f'Invalid {rule} format'
        return None

    def _validate_custom(self, field, value, rule):
        try:
            if not self.custom_validators[rule](value):
                return f'Validation failed for {field}'
        except Exception as e:
            return f'Validator error: {str(e)}'
        return None

    def _validate_dict_rule(self, field, value, rule):
        if 'type' not in rule:
            return None
        if rule['type'] != 'custom':
            return f"Unsupported rule type: {rule['type']}"
        return self._validate_inline_logic(field, value, rule)

    def _validate_inline_logic(self, field, value, rule):
        try:
            result = eval(rule['logic'], _build_eval_environment(value))
            if not result:
                return rule.get('message', f'Validation failed for {field}')
        except Exception as e:
            return f'Validation error: {str(e)}'
        return None


# ---------------------------------------------------------------------------
# Validator instance with built-in custom validators
# ---------------------------------------------------------------------------

validator = ConfigValidator()


def _register_builtin_validators():
    for name, logic in BUILTIN_CUSTOM_VALIDATORS.items():
        validator.add_custom_validator(name, logic)


_register_builtin_validators()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/api/validate', methods=['POST'])
def validate_config():
    try:
        data, error = _extract_payload(('config', 'rules'), MSG_CONFIG_AND_RULES_REQUIRED)
        if error:
            return error
        errors = validator.validate(data['config'], data['rules'])
        if errors:
            return jsonify({'valid': False, 'errors': errors})
        return jsonify({'valid': True})
    except Exception as e:
        return (jsonify({'error': str(e)}), HTTP_INTERNAL_SERVER_ERROR)


@app.route('/api/validator', methods=['POST'])
def create_validator():
    try:
        data, error = _extract_payload(('name', 'logic'), MSG_NAME_AND_LOGIC_REQUIRED)
        if error:
            return error
        if validator.add_custom_validator(data['name'], data['logic']):
            return jsonify({'status': MSG_VALIDATOR_ADDED})
        return (jsonify({'error': MSG_ADD_VALIDATOR_FAILED}), HTTP_BAD_REQUEST)
    except Exception as e:
        return (jsonify({'error': str(e)}), HTTP_BAD_REQUEST)


@app.route('/api/direct-validate', methods=['POST'])
def direct_validate():
    try:
        data, error = _extract_payload(('value', 'expression'), MSG_VALUE_AND_EXPRESSION_REQUIRED)
        if error:
            return error
        result = eval(data['expression'], _build_eval_environment(data['value']))
        return jsonify({'valid': bool(result)})
    except Exception as e:
        return (jsonify({'error': str(e)}), HTTP_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT)
