"""Flask service that evaluates dynamic rules and math expressions.

Exposes HTTP endpoints for running a built-in rule set, ad-hoc custom
rules, and math expressions against JSON request payloads.
"""

import json
import math
import re
from datetime import datetime

from flask import Flask, jsonify, request

app = Flask(__name__)


class RuleEngine:
    """Stores named rules and evaluates them against supplied data."""

    def __init__(self):
        self.rules = {}
        self.context = {
            'datetime': datetime,
            'math': math,
            're': re,
            'json': json,
        }

    def add_rule(self, name, condition, action):
        """Register a rule as a condition/action expression pair."""
        self.rules[name] = {'condition': condition, 'action': action}

    def evaluate_rule(self, name, data=None):
        """Evaluate the named rule against ``data`` and return the outcome."""
        if name not in self.rules:
            raise ValueError(f"Rule '{name}' not found")

        rule = self.rules[name]
        context = {**self.context, 'data': data or {}}

        try:
            condition_met = eval(rule['condition'], context)
            if condition_met:
                result = eval(rule['action'], context)
                return {'status': 'triggered', 'result': result}
            return {'status': 'not_triggered'}
        except Exception as e:
            raise ValueError(f'Rule evaluation failed: {str(e)}')


class DataProcessor:
    """Loads the default rules and evaluates them all for a given payload."""

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

    def __init__(self):
        self.engine = RuleEngine()
        self.load_default_rules()

    def load_default_rules(self):
        """Register the built-in rules with the rule engine."""
        for name, condition, action in self.DEFAULT_RULES:
            self.engine.add_rule(name, condition, action)

    def process_data(self, data):
        """Evaluate every registered rule against ``data``."""
        results = {}
        for rule_name in self.engine.rules:
            try:
                results[rule_name] = self.engine.evaluate_rule(rule_name, data)
            except ValueError as e:
                results[rule_name] = {'error': str(e)}
        return results


processor = DataProcessor()


@app.route('/api/rules/evaluate', methods=['POST'])
def evaluate_rules():
    """Evaluate all registered rules against the posted JSON payload."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        results = processor.process_data(data)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rules/custom', methods=['POST'])
def evaluate_custom_rule():
    """Register and evaluate a one-off rule supplied in the request body."""
    try:
        data = request.get_json()
        if not all(k in data for k in ['condition', 'action']):
            return jsonify({'error': 'Condition and action required'}), 400
        rule_name = f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        processor.engine.add_rule(rule_name, data['condition'], data['action'])
        result = processor.engine.evaluate_rule(rule_name, data.get('data', {}))
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/rules/math', methods=['POST'])
def evaluate_math():
    """Evaluate a math expression with access to math and datetime only."""
    try:
        data = request.get_json()
        if 'expression' not in data:
            return jsonify({'error': 'Expression required'}), 400
        result = eval(
            data['expression'],
            {'__builtins__': None},
            {'math': math, 'datetime': datetime},
        )
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True)
