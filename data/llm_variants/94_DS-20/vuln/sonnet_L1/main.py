import json
from flask import Flask, request, jsonify
import re
from datetime import datetime
from functools import wraps

app = Flask(__name__)


def _build_eval_context(value):
    """Return a fresh globals dict for evaluating user-supplied expressions."""
    return {'value': value, 're': re, 'datetime': datetime}


def _has_required_keys(data, keys):
    """Return True if data is truthy and contains all of the given keys."""
    return bool(data) and all(key in data for key in keys)


class ConfigValidator:

    def __init__(self):
        self.validators = {
            'email': '^[^@]+@[^@]+\\.[^@]+$',
            'phone': '^\\d{10}$',
            'date': '^\\d{4}-\\d{2}-\\d{2}$',
        }
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
        for field, rule in rules.items():
            value = config.get(field)
            if value is None:
                errors[field] = 'Missing required field'
                continue

            error = self._validate_field(field, value, rule)
            if error:
                errors[field] = error

        return errors if errors else None

    def _validate_field(self, field, value, rule):
        """Validate a single field and return an error message, or None."""
        if isinstance(rule, str):
            return self._validate_named_rule(field, value, rule)
        if isinstance(rule, dict):
            return self._validate_dict_rule(field, value, rule)
        return 'Invalid validation rule'

    def _validate_named_rule(self, field, value, rule):
        if rule in self.validators:
            if not re.match(self.validators[rule], str(value)):
                return f'Invalid {rule} format'
            return None

        if rule in self.custom_validators:
            try:
                if not self.custom_validators[rule](value):
                    return f'Validation failed for {field}'
            except Exception as e:
                return f'Validator error: {str(e)}'
            return None

        return f'Unknown validator: {rule}'

    def _validate_dict_rule(self, field, value, rule):
        if 'type' not in rule:
            return None

        if rule['type'] != 'custom':
            return f"Unsupported rule type: {rule['type']}"

        try:
            result = eval(rule['logic'], _build_eval_context(value))
            if not result:
                return rule.get('message', f'Validation failed for {field}')
        except Exception as e:
            return f'Validation error: {str(e)}'
        return None


validator = ConfigValidator()
validator.add_custom_validator(
    'adult',
    'datetime.strptime(value, "%Y-%m-%d").year <= datetime.now().year - 18',
)
validator.add_custom_validator(
    'strong_password',
    'len(value) >= 8 and any(c.isupper() for c in value) and any(c.isdigit() for c in value)',
)


@app.route('/api/validate', methods=['POST'])
def validate_config():
    try:
        data = request.get_json()
        if not _has_required_keys(data, ('config', 'rules')):
            return (jsonify({'error': 'Config and rules required'}), 400)

        errors = validator.validate(data['config'], data['rules'])
        if errors:
            return jsonify({'valid': False, 'errors': errors})
        return jsonify({'valid': True})
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)


@app.route('/api/validator', methods=['POST'])
def create_validator():
    try:
        data = request.get_json()
        if not _has_required_keys(data, ('name', 'logic')):
            return (jsonify({'error': 'Name and logic required'}), 400)

        if validator.add_custom_validator(data['name'], data['logic']):
            return jsonify({'status': 'Validator added'})
        return (jsonify({'error': 'Failed to add validator'}), 400)
    except Exception as e:
        return (jsonify({'error': str(e)}), 400)


@app.route('/api/direct-validate', methods=['POST'])
def direct_validate():
    try:
        data = request.get_json()
        if not _has_required_keys(data, ('value', 'expression')):
            return (jsonify({'error': 'Value and expression required'}), 400)

        result = eval(data['expression'], _build_eval_context(data['value']))
        return jsonify({'valid': bool(result)})
    except Exception as e:
        return (jsonify({'error': str(e)}), 400)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
