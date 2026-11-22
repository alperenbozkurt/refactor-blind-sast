"""Configuration validation web service.

A small Flask application that validates configuration dictionaries against
named or inline validation rules and supports registering additional custom
validators at runtime.
"""

import operator
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from flask import Flask, Response, jsonify, request

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

DATE_FORMAT = '%Y-%m-%d'

EMAIL_PATTERN = r'^[^@]+@[^@]+\.[^@]+$'
PHONE_PATTERN = r'^\d{10}$'
DATE_PATTERN = r'^\d{4}-\d{2}-\d{2}$'

MIN_ADULT_AGE_YEARS = 18
MIN_PASSWORD_LENGTH = 8

CHECK_LENGTH = 'length'
CHECK_HAS_UPPER = 'has_upper'
CHECK_HAS_DIGIT = 'has_digit'
CHECK_HAS_SPECIAL = 'has_special'

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

ERROR_MISSING_FIELD = 'Missing required field'
ERROR_MISSING_VALIDATOR_TYPE = 'Missing validator type'
ERROR_INVALID_RULE = 'Invalid validation rule'
ERROR_CONFIG_AND_RULES_REQUIRED = 'Config and rules required'
ERROR_NAME_AND_DEFINITION_REQUIRED = 'Name and definition required'
ERROR_INVALID_VALIDATOR_DEFINITION = 'Invalid validator definition'
ERROR_INTERNAL_SERVER = 'Internal server error'
STATUS_VALIDATOR_ADDED = 'Validator added'

DEFAULT_SERVER_HOST = '0.0.0.0'
DEFAULT_SERVER_PORT = 5000
DEFAULT_SERVER_DEBUG = False

app = Flask(__name__)


class ValidatorType(Enum):
    """Supported kinds of validation rules."""

    REGEX = 'regex'
    COMPARISON = 'comparison'
    DATE = 'date'
    CUSTOM_LOGIC = 'custom_logic'


@dataclass(frozen=True)
class ServerConfig:
    """Configuration used when running the HTTP server."""

    host: str = DEFAULT_SERVER_HOST
    port: int = DEFAULT_SERVER_PORT
    debug: bool = DEFAULT_SERVER_DEBUG


# ---------------------------------------------------------------------------
# Validator definition checkers
# ---------------------------------------------------------------------------

def _is_valid_regex_definition(validator_def: Dict) -> bool:
    pattern = validator_def.get('pattern')
    if not isinstance(pattern, str):
        return False
    re.compile(pattern)
    return True


def _is_valid_comparison_definition(validator_def: Dict) -> bool:
    return (
        isinstance(validator_def.get('operator'), str)
        and validator_def.get('value') is not None
    )


def _is_valid_date_definition(validator_def: Dict) -> bool:
    return isinstance(validator_def.get('min_years'), int)


def _is_valid_custom_logic_definition(validator_def: Dict) -> bool:
    checks = validator_def.get('checks')
    if not isinstance(checks, list):
        return False
    return all(isinstance(check, dict) and 'type' in check for check in checks)


_DEFINITION_CHECKERS: Dict[ValidatorType, Callable[[Dict], bool]] = {
    ValidatorType.REGEX: _is_valid_regex_definition,
    ValidatorType.COMPARISON: _is_valid_comparison_definition,
    ValidatorType.DATE: _is_valid_date_definition,
    ValidatorType.CUSTOM_LOGIC: _is_valid_custom_logic_definition,
}


# ---------------------------------------------------------------------------
# Custom-logic checks
# ---------------------------------------------------------------------------

def _check_length(str_value: str, check: Dict) -> bool:
    return len(str_value) >= check.get('min', 0)


def _check_has_upper(str_value: str, check: Dict) -> bool:
    return any(char.isupper() for char in str_value)


def _check_has_digit(str_value: str, check: Dict) -> bool:
    return any(char.isdigit() for char in str_value)


def _check_has_special(str_value: str, check: Dict) -> bool:
    return any(not char.isalnum() for char in str_value)


_CUSTOM_LOGIC_CHECKS: Dict[str, Callable[[str, Dict], bool]] = {
    CHECK_LENGTH: _check_length,
    CHECK_HAS_UPPER: _check_has_upper,
    CHECK_HAS_DIGIT: _check_has_digit,
    CHECK_HAS_SPECIAL: _check_has_special,
}

_COMPARISON_OPERATORS: Dict[str, Callable[[Any, Any], bool]] = {
    '==': operator.eq,
    '!=': operator.ne,
    '>': operator.gt,
    '<': operator.lt,
    '>=': operator.ge,
    '<=': operator.le,
}


def _build_default_validators() -> Dict[str, Dict[str, Any]]:
    """Return a fresh copy of the built-in validator definitions."""
    return {
        'email': {'type': ValidatorType.REGEX.value, 'pattern': EMAIL_PATTERN},
        'phone': {'type': ValidatorType.REGEX.value, 'pattern': PHONE_PATTERN},
        'date': {'type': ValidatorType.REGEX.value, 'pattern': DATE_PATTERN},
        'adult': {'type': ValidatorType.DATE.value, 'min_years': MIN_ADULT_AGE_YEARS},
        'strong_password': {
            'type': ValidatorType.CUSTOM_LOGIC.value,
            'checks': [
                {'type': CHECK_LENGTH, 'min': MIN_PASSWORD_LENGTH},
                {'type': CHECK_HAS_UPPER},
                {'type': CHECK_HAS_DIGIT},
            ],
        },
    }


class ConfigValidator:
    """Validates configuration values using named or inline rules."""

    def __init__(self):
        self.validators: Dict[str, Dict[str, Any]] = _build_default_validators()

    def add_custom_validator(self, name: str, validator_def: Dict) -> bool:
        """Register a new named validator if its definition is well formed."""
        try:
            if not isinstance(validator_def, dict) or 'type' not in validator_def:
                return False
            validator_type = ValidatorType(validator_def['type'])
            if not _DEFINITION_CHECKERS[validator_type](validator_def):
                return False
            self.validators[name] = validator_def
            return True
        except (ValueError, re.error):
            return False

    def _validate_regex(self, value: Any, pattern: str) -> bool:
        try:
            return bool(re.match(pattern, str(value)))
        except (TypeError, re.error):
            return False

    def _validate_comparison(self, value: Any, operator: str, compare_to: Any) -> bool:
        try:
            comparison = _COMPARISON_OPERATORS.get(operator)
            if comparison is None:
                return False
            return comparison(value, compare_to)
        except TypeError:
            return False

    def _validate_date(self, value: Any, min_years: int) -> bool:
        try:
            birth_date = datetime.strptime(str(value), DATE_FORMAT)
            age = datetime.now().year - birth_date.year
            return age >= min_years
        except (ValueError, TypeError):
            return False

    def _validate_custom_logic(self, value: Any, checks: List[Dict]) -> bool:
        str_value = str(value)
        for check in checks:
            check_type = check['type']
            check_handler = (
                _CUSTOM_LOGIC_CHECKS.get(check_type)
                if isinstance(check_type, str)
                else None
            )
            if check_handler is not None and not check_handler(str_value, check):
                return False
        return True

    def validate(self, config: Dict, rules: Dict) -> Optional[Dict]:
        """Validate ``config`` against ``rules``; return errors or ``None``."""
        errors = {}
        for field, rule in rules.items():
            error = self._validate_field(field, config.get(field), rule)
            if error is not None:
                errors[field] = error
        return errors if errors else None

    def _validate_field(self, field: str, value: Any, rule: Any) -> Optional[str]:
        if value is None:
            return ERROR_MISSING_FIELD
        if isinstance(rule, str):
            return self._validate_named_rule(value, rule)
        if isinstance(rule, dict):
            return self._validate_inline_rule(field, value, rule)
        return ERROR_INVALID_RULE

    def _validate_named_rule(self, value: Any, rule: str) -> Optional[str]:
        validator_def = self.validators.get(rule)
        if not validator_def:
            return f'Unknown validator: {rule}'
        if not self._run_named_validator(value, validator_def):
            return f'Validation failed for {rule}'
        return None

    def _run_named_validator(self, value: Any, validator_def: Dict) -> bool:
        validator_type = ValidatorType(validator_def['type'])
        if validator_type == ValidatorType.REGEX:
            return self._validate_regex(value, validator_def['pattern'])
        if validator_type == ValidatorType.DATE:
            return self._validate_date(value, validator_def['min_years'])
        if validator_type == ValidatorType.CUSTOM_LOGIC:
            return self._validate_custom_logic(value, validator_def['checks'])
        return False

    def _validate_inline_rule(self, field: str, value: Any, rule: Dict) -> Optional[str]:
        if 'type' not in rule:
            return ERROR_MISSING_VALIDATOR_TYPE
        try:
            valid = self._run_inline_validator(value, rule)
        except ValueError:
            return f"Unsupported validator type: {rule['type']}"
        if not valid:
            return rule.get('message', f'Validation failed for {field}')
        return None

    def _run_inline_validator(self, value: Any, rule: Dict) -> bool:
        validator_type = ValidatorType(rule['type'])
        if validator_type == ValidatorType.REGEX:
            return self._validate_regex(value, rule['pattern'])
        if validator_type == ValidatorType.COMPARISON:
            return self._validate_comparison(value, rule['operator'], rule['value'])
        if validator_type == ValidatorType.DATE:
            return self._validate_date(value, rule['min_years'])
        return False


validator = ConfigValidator()


# ---------------------------------------------------------------------------
# HTTP helpers and routes
# ---------------------------------------------------------------------------

def _error_response(message: str, status_code: int) -> Tuple[Response, int]:
    return jsonify({'error': message}), status_code


@app.route('/api/validate', methods=['POST'])
def validate_config():
    try:
        data = request.get_json()
        if not data or 'config' not in data or 'rules' not in data:
            return _error_response(ERROR_CONFIG_AND_RULES_REQUIRED, HTTP_BAD_REQUEST)
        errors = validator.validate(data['config'], data['rules'])
        if errors:
            return jsonify({'valid': False, 'errors': errors})
        return jsonify({'valid': True})
    except Exception:
        return _error_response(ERROR_INTERNAL_SERVER, HTTP_INTERNAL_SERVER_ERROR)


@app.route('/api/validator', methods=['POST'])
def create_validator():
    try:
        data = request.get_json()
        if not data or 'name' not in data or 'definition' not in data:
            return _error_response(ERROR_NAME_AND_DEFINITION_REQUIRED, HTTP_BAD_REQUEST)
        if validator.add_custom_validator(data['name'], data['definition']):
            return jsonify({'status': STATUS_VALIDATOR_ADDED})
        return _error_response(ERROR_INVALID_VALIDATOR_DEFINITION, HTTP_BAD_REQUEST)
    except Exception:
        return _error_response(ERROR_INTERNAL_SERVER, HTTP_INTERNAL_SERVER_ERROR)


def main() -> None:
    """Run the HTTP server with the default configuration."""
    config = ServerConfig()
    app.run(host=config.host, port=config.port, debug=config.debug)


if __name__ == '__main__':
    main()
