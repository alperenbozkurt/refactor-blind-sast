import json
import operator
from flask import Flask, request, jsonify
import re
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DATE_FORMAT = '%Y-%m-%d'

HOST = '0.0.0.0'
PORT = 5000
DEBUG = False

CHECK_LENGTH = 'length'
CHECK_HAS_UPPER = 'has_upper'
CHECK_HAS_DIGIT = 'has_digit'
CHECK_HAS_SPECIAL = 'has_special'

MSG_MISSING_FIELD = 'Missing required field'
MSG_MISSING_TYPE = 'Missing validator type'
MSG_INVALID_RULE = 'Invalid validation rule'
MSG_UNKNOWN_VALIDATOR = 'Unknown validator: {rule}'
MSG_VALIDATION_FAILED_RULE = 'Validation failed for {rule}'
MSG_VALIDATION_FAILED_FIELD = 'Validation failed for {field}'
MSG_UNSUPPORTED_TYPE = 'Unsupported validator type: {type}'

ERR_CONFIG_RULES_REQUIRED = 'Config and rules required'
ERR_NAME_DEFINITION_REQUIRED = 'Name and definition required'
ERR_INVALID_DEFINITION = 'Invalid validator definition'
ERR_INTERNAL = 'Internal server error'
STATUS_VALIDATOR_ADDED = 'Validator added'

COMPARISON_OPERATORS = {
    '==': operator.eq,
    '!=': operator.ne,
    '>': operator.gt,
    '<': operator.lt,
    '>=': operator.ge,
    '<=': operator.le,
}


class ValidatorType(Enum):
    REGEX = 'regex'
    COMPARISON = 'comparison'
    DATE = 'date'
    CUSTOM_LOGIC = 'custom_logic'


def _default_validators() -> Dict[str, Dict]:
    return {
        'email': {'type': ValidatorType.REGEX.value, 'pattern': '^[^@]+@[^@]+\\.[^@]+$'},
        'phone': {'type': ValidatorType.REGEX.value, 'pattern': '^\\d{10}$'},
        'date': {'type': ValidatorType.REGEX.value, 'pattern': '^\\d{4}-\\d{2}-\\d{2}$'},
        'adult': {'type': ValidatorType.DATE.value, 'min_years': 18},
        'strong_password': {
            'type': ValidatorType.CUSTOM_LOGIC.value,
            'checks': [
                {'type': CHECK_LENGTH, 'min': 8},
                {'type': CHECK_HAS_UPPER},
                {'type': CHECK_HAS_DIGIT},
            ],
        },
    }


# --------------------------------------------------------------------------- #
# Validator definition checks (used when registering custom validators)
# --------------------------------------------------------------------------- #
def _is_valid_regex_definition(validator_def: Dict) -> bool:
    if not isinstance(validator_def.get('pattern'), str):
        return False
    re.compile(validator_def['pattern'])
    return True


def _is_valid_comparison_definition(validator_def: Dict) -> bool:
    if not isinstance(validator_def.get('operator'), str):
        return False
    return validator_def.get('value') is not None


def _is_valid_date_definition(validator_def: Dict) -> bool:
    return isinstance(validator_def.get('min_years'), int)


def _is_valid_custom_logic_definition(validator_def: Dict) -> bool:
    if not isinstance(validator_def.get('checks'), list):
        return False
    for check in validator_def['checks']:
        if not isinstance(check, dict) or 'type' not in check:
            return False
    return True


_DEFINITION_CHECKERS = {
    ValidatorType.REGEX: _is_valid_regex_definition,
    ValidatorType.COMPARISON: _is_valid_comparison_definition,
    ValidatorType.DATE: _is_valid_date_definition,
    ValidatorType.CUSTOM_LOGIC: _is_valid_custom_logic_definition,
}


# --------------------------------------------------------------------------- #
# Custom-logic check helper
# --------------------------------------------------------------------------- #
def _run_custom_check(str_value: str, check: Dict) -> bool:
    check_type = check['type']
    if check_type == CHECK_LENGTH:
        return not len(str_value) < check.get('min', 0)
    if check_type == CHECK_HAS_UPPER:
        return any((c.isupper() for c in str_value))
    if check_type == CHECK_HAS_DIGIT:
        return any((c.isdigit() for c in str_value))
    if check_type == CHECK_HAS_SPECIAL:
        return any((not c.isalnum() for c in str_value))
    return True


class ConfigValidator:

    def __init__(self):
        self.validators = _default_validators()

    # ----------------------------- registration ---------------------------- #
    def add_custom_validator(self, name: str, validator_def: Dict) -> bool:
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

    # ----------------------------- primitives ------------------------------ #
    def _validate_regex(self, value: Any, pattern: str) -> bool:
        try:
            return bool(re.match(pattern, str(value)))
        except (TypeError, re.error):
            return False

    def _validate_comparison(self, value: Any, operator: str, compare_to: Any) -> bool:
        try:
            compare = COMPARISON_OPERATORS.get(operator)
            if compare is None:
                return False
            return compare(value, compare_to)
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
            if not _run_custom_check(str_value, check):
                return False
        return True

    # ----------------------------- rule handling --------------------------- #
    def _evaluate_named_rule(self, value: Any, validator_def: Dict) -> bool:
        validator_type = ValidatorType(validator_def['type'])
        if validator_type == ValidatorType.REGEX:
            return self._validate_regex(value, validator_def['pattern'])
        if validator_type == ValidatorType.DATE:
            return self._validate_date(value, validator_def['min_years'])
        if validator_type == ValidatorType.CUSTOM_LOGIC:
            return self._validate_custom_logic(value, validator_def['checks'])
        return False

    def _evaluate_inline_rule(self, value: Any, rule: Dict, validator_type: ValidatorType) -> bool:
        if validator_type == ValidatorType.REGEX:
            return self._validate_regex(value, rule['pattern'])
        if validator_type == ValidatorType.COMPARISON:
            return self._validate_comparison(value, rule['operator'], rule['value'])
        if validator_type == ValidatorType.DATE:
            return self._validate_date(value, rule['min_years'])
        return False

    def _check_named_rule(self, value: Any, rule: str) -> Optional[str]:
        """Return an error message, or None if the value is valid."""
        validator_def = self.validators.get(rule)
        if not validator_def:
            return MSG_UNKNOWN_VALIDATOR.format(rule=rule)
        if not self._evaluate_named_rule(value, validator_def):
            return MSG_VALIDATION_FAILED_RULE.format(rule=rule)
        return None

    def _check_inline_rule(self, field: str, value: Any, rule: Dict) -> Optional[str]:
        """Return an error message, or None if the value is valid."""
        if 'type' not in rule:
            return MSG_MISSING_TYPE
        try:
            validator_type = ValidatorType(rule['type'])
            valid = self._evaluate_inline_rule(value, rule, validator_type)
            if not valid:
                return rule.get('message', MSG_VALIDATION_FAILED_FIELD.format(field=field))
            return None
        except ValueError:
            return MSG_UNSUPPORTED_TYPE.format(type=rule['type'])

    def _check_field(self, field: str, value: Any, rule: Any) -> Optional[str]:
        if value is None:
            return MSG_MISSING_FIELD
        if isinstance(rule, str):
            return self._check_named_rule(value, rule)
        if isinstance(rule, dict):
            return self._check_inline_rule(field, value, rule)
        return MSG_INVALID_RULE

    # ----------------------------- public API ------------------------------ #
    def validate(self, config: Dict, rules: Dict) -> Optional[Dict]:
        errors = {}
        for (field, rule) in rules.items():
            error = self._check_field(field, config.get(field), rule)
            if error is not None:
                errors[field] = error
        return errors if errors else None


validator = ConfigValidator()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/api/validate', methods=['POST'])
def validate_config():
    try:
        data = request.get_json()
        if not data or 'config' not in data or 'rules' not in data:
            return (jsonify({'error': ERR_CONFIG_RULES_REQUIRED}), 400)
        errors = validator.validate(data['config'], data['rules'])
        if errors:
            return jsonify({'valid': False, 'errors': errors})
        return jsonify({'valid': True})
    except Exception as e:
        return (jsonify({'error': ERR_INTERNAL}), 500)


@app.route('/api/validator', methods=['POST'])
def create_validator():
    try:
        data = request.get_json()
        if not data or 'name' not in data or 'definition' not in data:
            return (jsonify({'error': ERR_NAME_DEFINITION_REQUIRED}), 400)
        if validator.add_custom_validator(data['name'], data['definition']):
            return jsonify({'status': STATUS_VALIDATOR_ADDED})
        return (jsonify({'error': ERR_INVALID_DEFINITION}), 400)
    except Exception:
        return (jsonify({'error': ERR_INTERNAL}), 500)


if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=DEBUG)
