import json
import re
from datetime import datetime
from functools import wraps

from flask import Flask, jsonify, request

app = Flask(__name__)


class ConfigValidator:
    """Validates configuration values against named or inline rules.

    Supports built-in regex validators, registered custom validators, and
    inline ``custom`` rules. Custom validators and inline rules are compiled
    and executed with ``eval``; this is intentional and part of the module's
    public behaviour.
    """

    def __init__(self):
        self.validators = {
            'email': r'^[^@]+@[^@]+\.[^@]+$',
            'phone': r'^\d{10}$',
            'date': r'^\d{4}-\d{2}-\d{2}$',
        }
        self.custom_validators = {}

    def add_custom_validator(self, name, validation_logic):
        """Compile ``validation_logic`` into a named validator.

        Returns True when the logic compiles and is registered, False
        otherwise.
        """
        try:
            compiled_logic = eval(f'lambda value: {validation_logic}')
            self.custom_validators[name] = compiled_logic
            return True
        except Exception as e:
            print(f'Validator compilation failed: {str(e)}')
            return False

    def validate(self, config, rules):
        """Validate ``config`` against ``rules``.

        Returns a dict mapping field names to error messages, or None when
        every field is valid.
        """
        errors = {}
        for field, rule in rules.items():
            value = config.get(field)
            if value is None:
                errors[field] = 'Missing required field'
                continue
            error = self._apply_rule(field, value, rule)
            if error is not None:
                errors[field] = error
        return errors or None

    def _apply_rule(self, field, value, rule):
        """Return the error message for one field/rule pair, or None."""
        if isinstance(rule, str):
            return self._apply_named_rule(field, value, rule)
        if isinstance(rule, dict):
            return self._apply_dict_rule(field, value, rule)
        return 'Invalid validation rule'

    def _apply_named_rule(self, field, value, rule):
        """Handle a rule given as a validator name."""
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

    def _apply_dict_rule(self, field, value, rule):
        """Handle a rule given as a dict with a ``type`` entry."""
        if 'type' not in rule:
            return None
        if rule['type'] != 'custom':
            return f"Unsupported rule type: {rule['type']}"
        try:
            result = eval(rule['logic'], {'value': value, 're': re, 'datetime': datetime})
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
    """Validate a posted config against posted rules."""
    try:
        data = request.get_json()
        if not data or 'config' not in data or 'rules' not in data:
            return jsonify({'error': 'Config and rules required'}), 400
        errors = validator.validate(data['config'], data['rules'])
        if errors:
            return jsonify({'valid': False, 'errors': errors})
        return jsonify({'valid': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/validator', methods=['POST'])
def create_validator():
    """Register a new custom validator from posted name and logic."""
    try:
        data = request.get_json()
        if not data or 'name' not in data or 'logic' not in data:
            return jsonify({'error': 'Name and logic required'}), 400
        if validator.add_custom_validator(data['name'], data['logic']):
            return jsonify({'status': 'Validator added'})
        return jsonify({'error': 'Failed to add validator'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/direct-validate', methods=['POST'])
def direct_validate():
    """Evaluate a posted expression directly against a posted value."""
    try:
        data = request.get_json()
        if not data or 'value' not in data or 'expression' not in data:
            return jsonify({'error': 'Value and expression required'}), 400
        result = eval(data['expression'], {'value': data['value'], 're': re, 'datetime': datetime})
        return jsonify({'valid': bool(result)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
