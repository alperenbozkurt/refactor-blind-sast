"""Flask micro-service for evaluating small Python-expression based rules."""

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime

from flask import Flask, jsonify, request

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Constants and configuration
# ---------------------------------------------------------------------------

STATUS_TRIGGERED = 'triggered'
STATUS_NOT_TRIGGERED = 'not_triggered'

RULE_NOT_FOUND_MESSAGE = "Rule '{name}' not found"
RULE_EVALUATION_FAILED_MESSAGE = 'Rule evaluation failed: {error}'

TEMP_RULE_PREFIX = 'temp_'
TEMP_RULE_TIMESTAMP_FORMAT = '%Y%m%d%H%M%S'
CUSTOM_RULE_REQUIRED_FIELDS = ('condition', 'action')


@dataclass(frozen=True)
class RuleSpec:
    """Immutable description of a named rule."""

    name: str
    condition: str
    action: str


DEFAULT_RULES = (
    RuleSpec(
        name='high_value_transaction',
        condition='data.get("amount", 0) > 10000',
        action='"ALERT: High value transaction: ${}".format(data.get("amount"))',
    ),
    RuleSpec(
        name='suspicious_login',
        condition='data.get("login_location") != data.get("usual_location")',
        action='"ALERT: Suspicious login from {}".format(data.get("login_location"))',
    ),
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def error_response(message, status_code):
    """Build a JSON error response paired with an HTTP status code."""
    return jsonify({'error': message}), status_code


def evaluate_math_expression(expression):
    """Evaluate a math expression in a builtins-free namespace."""
    return eval(expression, {'__builtins__': None}, {'math': math, 'datetime': datetime})


# ---------------------------------------------------------------------------
# Core domain classes
# ---------------------------------------------------------------------------

class RuleEngine:
    """Stores named rules and evaluates them against a data payload."""

    def __init__(self):
        self.rules = {}
        self.context = {'datetime': datetime, 'math': math, 're': re, 'json': json}

    def add_rule(self, name, condition, action):
        self.rules[name] = {'condition': condition, 'action': action}

    def evaluate_rule(self, name, data=None):
        if name not in self.rules:
            raise ValueError(RULE_NOT_FOUND_MESSAGE.format(name=name))
        rule = self.rules[name]
        context = {**self.context, 'data': data or {}}
        try:
            condition_met = eval(rule['condition'], context)
            if condition_met:
                result = eval(rule['action'], context)
                return {'status': STATUS_TRIGGERED, 'result': result}
            return {'status': STATUS_NOT_TRIGGERED}
        except Exception as e:
            raise ValueError(RULE_EVALUATION_FAILED_MESSAGE.format(error=str(e)))


class DataProcessor:
    """Evaluates every registered rule against incoming data."""

    def __init__(self):
        self.engine = RuleEngine()
        self.load_default_rules()

    def load_default_rules(self):
        for spec in DEFAULT_RULES:
            self.engine.add_rule(spec.name, spec.condition, spec.action)

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
# HTTP routes
# ---------------------------------------------------------------------------

@app.route('/api/rules/evaluate', methods=['POST'])
def evaluate_rules():
    try:
        data = request.get_json()
        if not data:
            return error_response('No data provided', 400)
        results = processor.process_data(data)
        return jsonify(results)
    except Exception as e:
        return error_response(str(e), 500)


@app.route('/api/rules/custom', methods=['POST'])
def evaluate_custom_rule():
    try:
        data = request.get_json()
        if not all((k in data for k in CUSTOM_RULE_REQUIRED_FIELDS)):
            return error_response('Condition and action required', 400)
        rule_name = TEMP_RULE_PREFIX + datetime.now().strftime(TEMP_RULE_TIMESTAMP_FORMAT)
        processor.engine.add_rule(rule_name, data['condition'], data['action'])
        result = processor.engine.evaluate_rule(rule_name, data.get('data', {}))
        return jsonify(result)
    except Exception as e:
        return error_response(str(e), 400)


@app.route('/api/rules/math', methods=['POST'])
def evaluate_math():
    try:
        data = request.get_json()
        if 'expression' not in data:
            return error_response('Expression required', 400)
        result = evaluate_math_expression(data['expression'])
        return jsonify({'result': result})
    except Exception as e:
        return error_response(str(e), 400)


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main():
    app.run(debug=True)


if __name__ == '__main__':
    main()
