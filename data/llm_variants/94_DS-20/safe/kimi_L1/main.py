"""Flask web service for validating configuration data against named or inline rules."""

import json
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request

app = Flask(__name__)


class ValidatorType(Enum):
    """Kinds of validation rules supported by ConfigValidator."""

    REGEX = 'regex'
    COMPARISON = 'comparison'
    DATE = 'date'
    CUSTOM_LOGIC = 'custom_logic'


class ConfigValidator:
    """Validates configuration values using built-in and custom validator definitions."""

    def __init__(self):
        self.validators = {
            'email': {
                'type': ValidatorType.REGEX.value,
                'pattern': r'^[^@]+@[^@]+\.[^@]+$',
            },
            'phone': {
                'type': ValidatorType.REGEX.value,
                'pattern': r'^\d{10}$',
            },
            'date': {
                'type': ValidatorType.REGEX.value,
                'pattern': r'^\d{4}-\d{2}-\d{2}$',
            },
            'adult': {
                'type': ValidatorType.DATE.value,
                'min_years': 18,
            },
            'strong_password': {
                'type': ValidatorType.CUSTOM_LOGIC.value,
                'checks': [
                    {'type': 'length', 'min': 8},
                    {'type': 'has_upper'},
                    {'type': 'has_digit'},
                ],
            },
        }

    def add_custom_validator(self, name: str, validator_def: Dict) -> bool:
        try:
            if not isinstance(validator_def, dict) or 'type' not in validator_def:
                return False
            validator_type = ValidatorType(validator_def['type'])
            if not self._is_valid_definition(validator_type, validator_def):
                return False
            self.validators[name] = validator_def
            return True
        except (ValueError, re.error):
            return False

    def _is_valid_definition(self, validator_type: ValidatorType, validator_def: Dict) -> bool:
        if validator_type == ValidatorType.REGEX:
            pattern = validator_def.get('pattern')
            if not isinstance(pattern, str):
                return False
            re.compile(pattern)
            return True
        if validator_type == ValidatorType.COMPARISON:
            return (
                isinstance(validator_def.get('operator'), str)
                and validator_def.get('value') is not None
            )
        if validator_type == ValidatorType.DATE:
            return isinstance(validator_def.get('min_years'), int)
        if validator_type == ValidatorType.CUSTOM_LOGIC:
            checks = validator_def.get('checks')
            return isinstance(checks, list) and all(
                isinstance(check, dict) and 'type' in check for check in checks
            )
        return False

    def _validate_regex(self, value: Any, pattern: str) -> bool:
        try:
            return bool(re.match(pattern, str(value)))
        except (TypeError, re.error):
            return False

    def _validate_comparison(self, value: Any, operator: str, compare_to: Any) -> bool:
        try:
            if operator == '==':
                return value == compare_to
            if operator == '!=':
                return value != compare_to
            if operator == '>':
                return value > compare_to
            if operator == '<':
                return value < compare_to
            if operator == '>=':
                return value >= compare_to
            if operator == '<=':
                return value <= compare_to
            return False
        except TypeError:
            return False

    def _validate_date(self, value: Any, min_years: int) -> bool:
        try:
            birth_date = datetime.strptime(str(value), '%Y-%m-%d')
            age = datetime.now().year - birth_date.year
            return age >= min_years
        except (ValueError, TypeError):
            return False

    def _validate_custom_logic(self, value: Any, checks: List[Dict]) -> bool:
        str_value = str(value)
        for check in checks:
            check_type = check['type']
            if check_type == 'length' and len(str_value) < check.get('min', 0):
                return False
            if check_type == 'has_upper' and not any(c.isupper() for c in str_value):
                return False
            if check_type == 'has_digit' and not any(c.isdigit() for c in str_value):
                return False
            if check_type == 'has_special' and not any(not c.isalnum() for c in str_value):
                return False
        return True

    def validate(self, config: Dict, rules: Dict) -> Optional[Dict]:
        errors = {}
        for field, rule in rules.items():
            value = config.get(field)
            if value is None:
                errors[field] = 'Missing required field'
                continue
            if isinstance(rule, str):
                error = self._validate_with_named_rule(field, value, rule)
            elif isinstance(rule, dict):
                error = self._validate_with_inline_rule(field, value, rule)
            else:
                error = 'Invalid validation rule'
            if error is not None:
                errors[field] = error
        return errors or None

    def _validate_with_named_rule(self, field: str, value: Any, rule: str) -> Optional[str]:
        validator_def = self.validators.get(rule)
        if not validator_def:
            return f'Unknown validator: {rule}'
        if not self._apply_named_validator(value, validator_def):
            return f'Validation failed for {rule}'
        return None

    def _apply_named_validator(self, value: Any, validator_def: Dict) -> bool:
        validator_type = ValidatorType(validator_def['type'])
        if validator_type == ValidatorType.REGEX:
            return self._validate_regex(value, validator_def['pattern'])
        if validator_type == ValidatorType.DATE:
            return self._validate_date(value, validator_def['min_years'])
        if validator_type == ValidatorType.CUSTOM_LOGIC:
            return self._validate_custom_logic(value, validator_def['checks'])
        return False

    def _validate_with_inline_rule(self, field: str, value: Any, rule: Dict) -> Optional[str]:
        if 'type' not in rule:
            return 'Missing validator type'
        try:
            valid = self._apply_inline_validator(value, rule)
            if not valid:
                return rule.get('message', f'Validation failed for {field}')
            return None
        except ValueError:
            return f"Unsupported validator type: {rule['type']}"

    def _apply_inline_validator(self, value: Any, rule: Dict) -> bool:
        validator_type = ValidatorType(rule['type'])
        if validator_type == ValidatorType.REGEX:
            return self._validate_regex(value, rule['pattern'])
        if validator_type == ValidatorType.COMPARISON:
            return self._validate_comparison(value, rule['operator'], rule['value'])
        if validator_type == ValidatorType.DATE:
            return self._validate_date(value, rule['min_years'])
        return False


validator = ConfigValidator()


@app.route('/api/validate', methods=['POST'])
def validate_config():
    try:
        data = request.get_json()
        if not data or 'config' not in data or 'rules' not in data:
            return (jsonify({'error': 'Config and rules required'}), 400)
        errors = validator.validate(data['config'], data['rules'])
        if errors:
            return jsonify({'valid': False, 'errors': errors})
        return jsonify({'valid': True})
    except Exception:
        return (jsonify({'error': 'Internal server error'}), 500)


@app.route('/api/validator', methods=['POST'])
def create_validator():
    try:
        data = request.get_json()
        if not data or 'name' not in data or 'definition' not in data:
            return (jsonify({'error': 'Name and definition required'}), 400)
        if validator.add_custom_validator(data['name'], data['definition']):
            return jsonify({'status': 'Validator added'})
        return (jsonify({'error': 'Invalid validator definition'}), 400)
    except Exception:
        return (jsonify({'error': 'Internal server error'}), 500)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
