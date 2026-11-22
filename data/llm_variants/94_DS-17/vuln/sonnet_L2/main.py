import json
import math
import re
from datetime import datetime

from flask import Flask, request, jsonify

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

TEMP_RULE_PREFIX = 'temp_'
TEMP_RULE_TIMESTAMP_FORMAT = '%Y%m%d%H%M%S'

STATUS_TRIGGERED = 'triggered'
STATUS_NOT_TRIGGERED = 'not_triggered'

CUSTOM_RULE_REQUIRED_FIELDS = ('condition', 'action')

MSG_NO_DATA = 'No data provided'
MSG_CONDITION_ACTION_REQUIRED = 'Condition and action required'
MSG_EXPRESSION_REQUIRED = 'Expression required'

DEFAULT_RULES = (
    (
        'high_value_transaction',
        'data.get("amount", 0) > 10000',
        '"ALERT: High value transaction: ${}".format(data.get("amount"))',
    ),
    (
        'suspicious_login',
        'data.get("login_location") != data.get("usual_location")',
        '"ALERT: Suspicious login from {}".format(data.get("login_location"))',
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(message, status_code):
    """Build a JSON error response tuple."""
    return (jsonify({'error': message}), status_code)


def _generate_temp_rule_name():
    """Create a timestamp-based name for a temporary rule."""
    return TEMP_RULE_PREFIX + datetime.now().strftime(TEMP_RULE_TIMESTAMP_FORMAT)


def _has_required_fields(payload, fields):
    """Return True if every field name is present in the payload."""
    return all((field in payload for field in fields))


def _build_math_namespaces():
    """Return (globals, locals) namespaces for math expression evaluation."""
    return ({'__builtins__': None}, {'math': math, 'datetime': datetime})


# ---------------------------------------------------------------------------
# Core domain classes
#
# NOTE: Rules are evaluated with eval(); conditions, actions and expressions
# are therefore executable code. Only expose these endpoints to trusted
# callers, or replace eval with a sandboxed expression evaluator.
# ---------------------------------------------------------------------------

class RuleEngine:

    def __init__(self):
        self.rules = {}
        self.context = self._build_default_context()

    @staticmethod
    def _build_default_context():
        return {'datetime': datetime, 'math': math, 're': re, 'json': json}

    def add_rule(self, name, condition, action):
        self.rules[name] = {'condition': condition, 'action': action}

    def _build_context(self, data):
        return {**self.context, 'data': data or {}}

    def evaluate_rule(self, name, data=None):
        if name not in self.rules:
            raise ValueError(f"Rule '{name}' not found")
        rule = self.rules[name]
        context = self._build_context(data)
        try:
            return self._run_rule(rule, context)
        except Exception as e:
            raise ValueError(f'Rule evaluation failed: {str(e)}')

    @staticmethod
    def _run_rule(rule, context):
        condition_met = eval(rule['condition'], context)
        if condition_met:
            result = eval(rule['action'], context)
            return {'status': STATUS_TRIGGERED, 'result': result}
        return {'status': STATUS_NOT_TRIGGERED}


class DataProcessor:

    def __init__(self):
        self.engine = RuleEngine()
        self.load_default_rules()

    def load_default_rules(self):
        for name, condition, action in DEFAULT_RULES:
            self.engine.add_rule(name, condition, action)

    def process_data(self, data):
        results = {}
        for rule_name in self.engine.rules:
            try:
                results[rule_name] = self.engine.evaluate_rule(rule_name, data)
            except ValueError as e:
                results[rule_name] = {'error': str(e)}
        return results


processor = DataProcessor()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/api/rules/evaluate', methods=['POST'])
def evaluate_rules():
    try:
        data = request.get_json()
        if not data:
            return _error_response(MSG_NO_DATA, HTTP_BAD_REQUEST)
        results = processor.process_data(data)
        return jsonify(results)
    except Exception as e:
        return _error_response(str(e), HTTP_INTERNAL_SERVER_ERROR)


@app.route('/api/rules/custom', methods=['POST'])
def evaluate_custom_rule():
    try:
        data = request.get_json()
        if not _has_required_fields(data, CUSTOM_RULE_REQUIRED_FIELDS):
            return _error_response(MSG_CONDITION_ACTION_REQUIRED, HTTP_BAD_REQUEST)
        rule_name = _generate_temp_rule_name()
        processor.engine.add_rule(rule_name, data['condition'], data['action'])
        result = processor.engine.evaluate_rule(rule_name, data.get('data', {}))
        return jsonify(result)
    except Exception as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)


@app.route('/api/rules/math', methods=['POST'])
def evaluate_math():
    try:
        data = request.get_json()
        if 'expression' not in data:
            return _error_response(MSG_EXPRESSION_REQUIRED, HTTP_BAD_REQUEST)
        eval_globals, eval_locals = _build_math_namespaces()
        result = eval(data['expression'], eval_globals, eval_locals)
        return jsonify({'result': result})
    except Exception as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)


if __name__ == '__main__':
    app.run(debug=True)
