import json
import operator
import re
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from flask import Flask, request, jsonify

app = Flask(__name__)


class ValidatorType(Enum):
    REGEX = 'regex'
    COMPARISON = 'comparison'
    DATE = 'date'
    CUSTOM_LOGIC = 'custom_logic'


COMPARISON_OPERATORS: Dict[str, Callable[[Any, Any], Any]] = {
    '==': operator.eq,
    '!=': operator.ne,
    '>': operator.gt,
    '<': operator.lt,
    '>=': operator.ge,
    '<=': operator.le,
}


class ConfigValidator:

    def __init__(self):
        self.validators = {
            'email': {
                'type': ValidatorType.REGEX.value,
                'pattern': '^[^@]+@[^@]+\\.[^@]+$',
            },
            'phone': {
                'type': ValidatorType.REGEX.value,
                'pattern': '^\\d{10}$',
            },
            'date': {
                'type': ValidatorType.REGEX.value,
                'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
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

    # ------------------------------------------------------------------
    # Validator registration
    # ------------------------------------------------------------------

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

    @staticmethod
    def _is_valid_definition(validator_type: ValidatorType, validator_def: Dict) -> bool:
        """Check the type-specific structure of a validator definition."""
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

    # ------------------------------------------------------------------
    # Individual validators
    # ------------------------------------------------------------------

    def _validate_regex(self, value: Any, pattern: str) -> bool:
        try:
            return bool(re.match(pattern, str(value)))
        except (TypeError, re.error):
            return False

    def _validate_comparison(self, value: Any, operator: str, compare_to: Any) -> bool:
        compare = COMPARISON_OPERATORS.get(operator)
        if compare is None:
            return False
        try:
            return compare(value, compare_to)
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
            if not self._run_check(str_value, check):
                return False
        return True

    @staticmethod
    def _run_check(str_value: str, check: Dict) -> bool:
        """Run a single custom-logic check against a string value."""
        check_type = check['type']
        if check_type == 'length':
            return not len(str_value) < check.get('min', 0)
        if check_type == 'has_upper':
            return any(c.isupper() for c in str_value)
        if check_type == 'has_digit':
            return any(c.isdigit() for c in str_value)
        if check_type == 'has_special':
            return any(not c.isalnum() for c in str_value)
        return True

    # ------------------------------------------------------------------
    # Rule evaluation
    # ------------------------------------------------------------------

    def _check_named_rule(self, value: Any, validator_def: Dict) -> bool:
        """Evaluate a value against a registered (named) validator."""
        validator_type = ValidatorType(validator_def['type'])
        if validator_type == ValidatorType.REGEX:
            return self._validate_regex(value, validator_def['pattern'])
        if validator_type == ValidatorType.DATE:
            return self._validate_date(value, validator_def['min_years'])
        if validator_type == ValidatorType.CUSTOM_LOGIC:
            return self._validate_custom_logic(value, validator_def['checks'])
        return False

    def _check_inline_rule(self, value: Any, rule: Dict) -> bool:
        """Evaluate a value against an inline rule definition."""
        validator_type = ValidatorType(rule['type'])
        if validator_type == ValidatorType.REGEX:
            return self._validate_regex(value, rule['pattern'])
        if validator_type == ValidatorType.COMPARISON:
            return self._validate_comparison(value, rule['operator'], rule['value'])
        if validator_type == ValidatorType.DATE:
            return self._validate_date(value, rule['min_years'])
        return False

    def _validate_field(self, field: str, value: Any, rule: Any) -> Optional[str]:
        """Return an error message for the field, or None if it is valid."""
        if isinstance(rule, str):
            validator_def = self.validators.get(rule)
            if not validator_def:
                return f'Unknown validator: {rule}'
            if not self._check_named_rule(value, validator_def):
                return f'Validation failed for {rule}'
            return None

        if isinstance(rule, dict):
            if 'type' not in rule:
                return 'Missing validator type'
            try:
                if not self._check_inline_rule(value, rule):
                    return rule.get('message', f'Validation failed for {field}')
            except ValueError:
                return f"Unsupported validator type: {rule['type']}"
            return None

        return 'Invalid validation rule'

    def validate(self, config: Dict, rules: Dict) -> Optional[Dict]:
        errors = {}
        for field, rule in rules.items():
            value = config.get(field)
            if value is None:
                errors[field] = 'Missing required field'
                continue
            error = self._validate_field(field, value, rule)
            if error is not None:
                errors[field] = error
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
