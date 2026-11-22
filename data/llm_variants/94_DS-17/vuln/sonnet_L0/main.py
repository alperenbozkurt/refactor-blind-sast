import json
import math
import re
from datetime import datetime

from flask import Flask, request, jsonify

app = Flask(__name__)


class RuleEngine:

    def __init__(self):
        self.rules = {}
        self.context = {'datetime': datetime, 'math': math, 're': re, 'json': json}

    def add_rule(self, name, condition, action):
        self.rules[name] = {'condition': condition, 'action': action}

    def evaluate_rule(self, name, data=None):
        if name not in self.rules:
            raise ValueError(f"Rule '{name}' not found")
        rule = self.rules[name]
        context = {**self.context, 'data': data or {}}
        try:
            if not eval(rule['condition'], context):
                return {'status': 'not_triggered'}
            result = eval(rule['action'], context)
            return {'status': 'triggered', 'result': result}
        except Exception as e:
            raise ValueError(f'Rule evaluation failed: {str(e)}')


class DataProcessor:

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
        for name, condition, action in self.DEFAULT_RULES:
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


def _error_response(message, status):
    return (jsonify({'error': message}), status)


@app.route('/api/rules/evaluate', methods=['POST'])
def evaluate_rules():
    try:
        data = request.get_json()
        if not data:
            return _error_response('No data provided', 400)
        return jsonify(processor.process_data(data))
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/api/rules/custom', methods=['POST'])
def evaluate_custom_rule():
    try:
        data = request.get_json()
        if not all(k in data for k in ('condition', 'action')):
            return _error_response('Condition and action required', 400)
        rule_name = 'temp_' + datetime.now().strftime('%Y%m%d%H%M%S')
        processor.engine.add_rule(rule_name, data['condition'], data['action'])
        result = processor.engine.evaluate_rule(rule_name, data.get('data', {}))
        return jsonify(result)
    except Exception as e:
        return _error_response(str(e), 400)


@app.route('/api/rules/math', methods=['POST'])
def evaluate_math():
    try:
        data = request.get_json()
        if 'expression' not in data:
            return _error_response('Expression required', 400)
        result = eval(
            data['expression'],
            {'__builtins__': None},
            {'math': math, 'datetime': datetime},
        )
        return jsonify({'result': result})
    except Exception as e:
        return _error_response(str(e), 400)


if __name__ == '__main__':
    app.run(debug=True)
