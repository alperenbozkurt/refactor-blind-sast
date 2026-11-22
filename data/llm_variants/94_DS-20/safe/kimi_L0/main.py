"""Flask service for validating configuration values against reusable rules."""

import copy
import json
import operator
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request

app = Flask(__name__)


class ValidatorType(Enum):
    REGEX = 'regex'
    COMPARISON = 'comparison'
    DATE = 'date'
    CUSTOM_LOGIC = 'custom_logic'


_COMPARISON_OPERATORS = {
    '==': operator.eq,
    '!=': operator.ne,
    '>': operator.gt,
    '<': operator.lt,
    '>=': operator.ge,
    '<=': operator.le,
}


class ConfigValidator:
    """Validates configuration dictionaries against named or inline rules."""

    DEFAULT_VALIDATORS = {
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

    _CUSTOM_CHECKS = {
        'has_upper': lambda text: any(char.isupper() for char in text),
        'has_digit': lambda text: any(char.isdigit() for char in text),
        'has_special': lambda text: any(not char.isalnum() for char in text),
    }

    def __init__(self):
        self.validators = copy.deepcopy(self.DEFAULT_VALIDATORS)

    def add_custom_validator(self, name: str, validator_def: Dict) -> bool:
        try:
            if not isinstance(validator_def, dict) or 'type' not in validator_def:
                return False
            validator_type = ValidatorType(validator_def['type'])
            if not self._definition_is_valid(validator_type, validator_def):
                return False
            self.validators[name] = validator_def
            return True
        except (ValueError, re.error):
            return False

    @staticmethod
    def _definition_is_valid(validator_type: ValidatorType, validator_def: Dict) -> bool:
        if validator_type == ValidatorType.REGEX:
            if not isinstance(validator_def.get('pattern'), str):
                return False
            re.compile(validator_def['pattern'])
        elif validator_type == ValidatorType.COMPARISON:
            if not isinstance(validator_def.get('operator'), str):
                return False
            if validator_def.get('value') is None:
                return False
        elif validator_type == ValidatorType.DATE:
            if not isinstance(validator_def.get('min_years'), int):
                return False
        elif validator_type == ValidatorType.CUSTOM_LOGIC:
            if not isinstance(validator_def.get('checks'), list):
                return False
            for check in validator_def['checks']:
                if not isinstance(check, dict) or 'type' not in check:
                    return False
        return True

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
            birth_date = datetime.strptime(str(value), '%Y-%m-%d')
            age = datetime.now().year - birth_date.year
            return age >= min_years
        except (ValueError, TypeError):
            return False

    def _validate_custom_logic(self, value: Any, checks: List[Dict]) -> bool:
        str_value = str(value)
        for check in checks:
            check_type = check['type']
            if check_type == 'length':
                if len(str_value) < check.get('min', 0):
                    return False
                continue
            predicate = self._CUSTOM_CHECKS.get(check_type)
            if predicate is not None and not predicate(str_value):
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
                error = self._validate_named_rule(value, rule)
            elif isinstance(rule, dict):
                error = self._validate_inline_rule(field, value, rule)
            else:
                error = 'Invalid validation rule'
            if error is not None:
                errors[field] = error
        return errors or None

    def _validate_named_rule(self, value: Any, rule: str) -> Optional[str]:
        validator_def = self.validators.get(rule)
        if not validator_def:
            return f'Unknown validator: {rule}'
        validator_type = ValidatorType(validator_def['type'])
        valid = False
        if validator_type == ValidatorType.REGEX:
            valid = self._validate_regex(value, validator_def['pattern'])
        elif validator_type == ValidatorType.DATE:
            valid = self._validate_date(value, validator_def['min_years'])
        elif validator_type == ValidatorType.CUSTOM_LOGIC:
            valid = self._validate_custom_logic(value, validator_def['checks'])
        if not valid:
            return f'Validation failed for {rule}'
        return None

    def _validate_inline_rule(self, field: str, value: Any, rule: Dict) -> Optional[str]:
        if 'type' not in rule:
            return 'Missing validator type'
        try:
            validator_type = ValidatorType(rule['type'])
            valid = False
            if validator_type == ValidatorType.REGEX:
                valid = self._validate_regex(value, rule['pattern'])
            elif validator_type == ValidatorType.COMPARISON:
                valid = self._validate_comparison(value, rule['operator'], rule['value'])
            elif validator_type == ValidatorType.DATE:
                valid = self._validate_date(value, rule['min_years'])
        except ValueError:
            return f"Unsupported validator type: {rule['type']}"
        if not valid:
            return rule.get('message', f'Validation failed for {field}')
        return None


validator = ConfigValidator()


@app.route('/api/validate', methods=['POST'])
def validate_config():
    try:
        data = request.get_json()
        if not data or 'config' not in data or 'rules' not in data:
            return jsonify({'error': 'Config and rules required'}), 400
        errors = validator.validate(data['config'], data['rules'])
        if errors:
            return jsonify({'valid': False, 'errors': errors})
        return jsonify({'valid': True})
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/validator', methods=['POST'])
def create_validator():
    try:
        data = request.get_json()
        if not data or 'name' not in data or 'definition' not in data:
            return jsonify({'error': 'Name and definition required'}), 400
        if validator.add_custom_validator(data['name'], data['definition']):
            return jsonify({'status': 'Validator added'})
        return jsonify({'error': 'Invalid validator definition'}), 400
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
