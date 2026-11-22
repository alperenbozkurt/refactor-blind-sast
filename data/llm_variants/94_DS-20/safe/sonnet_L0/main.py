import json
import operator as _op
from flask import Flask, request, jsonify
import re
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional

app = Flask(__name__)


class ValidatorType(Enum):
    REGEX = 'regex'
    COMPARISON = 'comparison'
    DATE = 'date'
    CUSTOM_LOGIC = 'custom_logic'


_COMPARISON_OPERATORS = {
    '==': _op.eq,
    '!=': _op.ne,
    '>': _op.gt,
    '<': _op.lt,
    '>=': _op.ge,
    '<=': _op.le,
}


class ConfigValidator:

    def __init__(self):
        self.validators = {
            'email': {'type': ValidatorType.REGEX.value, 'pattern': '^[^@]+@[^@]+\\.[^@]+$'},
            'phone': {'type': ValidatorType.REGEX.value, 'pattern': '^\\d{10}$'},
            'date': {'type': ValidatorType.REGEX.value, 'pattern': '^\\d{4}-\\d{2}-\\d{2}$'},
            'adult': {'type': ValidatorType.DATE.value, 'min_years': 18},
            'strong_password': {
                'type': ValidatorType.CUSTOM_LOGIC.value,
                'checks': [{'type': 'length', 'min': 8}, {'type': 'has_upper'}, {'type': 'has_digit'}],
            },
        }

    @staticmethod
    def _is_definition_valid(validator_type: ValidatorType, validator_def: Dict) -> bool:
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
            checks = validator_def.get('checks')
            if not isinstance(checks, list):
                return False
            if not all(isinstance(check, dict) and 'type' in check for check in checks):
                return False
        return True

    def add_custom_validator(self, name: str, validator_def: Dict) -> bool:
        try:
            if not isinstance(validator_def, dict) or 'type' not in validator_def:
                return False
            validator_type = ValidatorType(validator_def['type'])
            if not self._is_definition_valid(validator_type, validator_def):
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
        func = _COMPARISON_OPERATORS.get(operator)
        if func is None:
            return False
        try:
            return func(value, compare_to)
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
        check_functions = {
            'has_upper': lambda s: any(c.isupper() for c in s),
            'has_digit': lambda s: any(c.isdigit() for c in s),
            'has_special': lambda s: any(not c.isalnum() for c in s),
        }
        for check in checks:
            check_type = check['type']
            if check_type == 'length':
                if len(str_value) < check.get('min', 0):
                    return False
            elif check_type in check_functions:
                if not check_functions[check_type](str_value):
                    return False
        return True

    def _check_named_validator(self, value: Any, validator_def: Dict) -> bool:
        validator_type = ValidatorType(validator_def['type'])
        if validator_type == ValidatorType.REGEX:
            return self._validate_regex(value, validator_def['pattern'])
        if validator_type == ValidatorType.DATE:
            return self._validate_date(value, validator_def['min_years'])
        if validator_type == ValidatorType.CUSTOM_LOGIC:
            return self._validate_custom_logic(value, validator_def['checks'])
        return False

    def _check_inline_rule(self, value: Any, validator_type: ValidatorType, rule: Dict) -> bool:
        if validator_type == ValidatorType.REGEX:
            return self._validate_regex(value, rule['pattern'])
        if validator_type == ValidatorType.COMPARISON:
            return self._validate_comparison(value, rule['operator'], rule['value'])
        if validator_type == ValidatorType.DATE:
            return self._validate_date(value, rule['min_years'])
        return False

    def validate(self, config: Dict, rules: Dict) -> Optional[Dict]:
        errors = {}
        for field, rule in rules.items():
            value = config.get(field)
            if value is None:
                errors[field] = 'Missing required field'
                continue
            if isinstance(rule, str):
                validator_def = self.validators.get(rule)
                if not validator_def:
                    errors[field] = f'Unknown validator: {rule}'
                    continue
                if not self._check_named_validator(value, validator_def):
                    errors[field] = f'Validation failed for {rule}'
            elif isinstance(rule, dict):
                if 'type' not in rule:
                    errors[field] = 'Missing validator type'
                    continue
                try:
                    validator_type = ValidatorType(rule['type'])
                    if not self._check_inline_rule(value, validator_type, rule):
                        errors[field] = rule.get('message', f'Validation failed for {field}')
                except ValueError:
                    errors[field] = f"Unsupported validator type: {rule['type']}"
            else:
                errors[field] = 'Invalid validation rule'
        return errors if errors else None


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
    except Exception as e:
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
