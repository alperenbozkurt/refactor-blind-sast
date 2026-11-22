"""Flask API exposing a safe rule engine and a safe math evaluator."""

import json
import math
from datetime import datetime
from enum import Enum
from typing import Any, Dict

from flask import Flask, jsonify, request

app = Flask(__name__)


class RuleType(Enum):
    COMPARISON = 'comparison'
    RANGE_CHECK = 'range_check'
    STRING_MATCH = 'string_match'


class SafeRuleEngine:
    """Evaluates a fixed set of rule types without executing arbitrary code."""

    _COMPARISON_OPERATORS = {
        '==': lambda a, b: a == b,
        '!=': lambda a, b: a != b,
        '>': lambda a, b: a > b,
        '<': lambda a, b: a < b,
        '>=': lambda a, b: a >= b,
        '<=': lambda a, b: a <= b,
    }

    def __init__(self):
        self.rules: Dict[str, Dict] = {}
        self.load_default_rules()

    def add_rule(self, name: str, rule_type: RuleType, params: Dict[str, Any]) -> None:
        if not isinstance(params, dict):
            raise ValueError('Rule params must be a dictionary')
        self.rules[name] = {'type': rule_type, 'params': params}

    def load_default_rules(self) -> None:
        self.add_rule(
            'high_value_transaction',
            RuleType.RANGE_CHECK,
            {'field': 'amount', 'min': 10000},
        )
        self.add_rule(
            'suspicious_login',
            RuleType.COMPARISON,
            {'field1': 'login_location', 'field2': 'usual_location', 'operator': '!='},
        )

    def evaluate_rule(self, name: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        if name not in self.rules:
            raise ValueError(f"Rule '{name}' not found")
        rule = self.rules[name]
        data = data or {}
        try:
            if rule['type'] == RuleType.COMPARISON:
                return self._evaluate_comparison(rule, data)
            if rule['type'] == RuleType.RANGE_CHECK:
                return self._evaluate_range_check(rule, data)
            if rule['type'] == RuleType.STRING_MATCH:
                return self._evaluate_string_match(rule, data)
            return {'status': 'not_triggered'}
        except Exception as e:
            raise ValueError(f'Rule evaluation error: {str(e)}')

    def _evaluate_comparison(self, rule: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        params = rule['params']
        val1 = data.get(params['field1'])
        val2 = data.get(params['field2'])
        op = params['operator']
        compare = self._COMPARISON_OPERATORS.get(op)
        if compare is None:
            raise ValueError(f'Invalid operator: {op}')
        if compare(val1, val2):
            return {
                'status': 'triggered',
                'message': f"Condition met: {params['field1']} {op} {params['field2']}",
            }
        return {'status': 'not_triggered'}

    def _evaluate_range_check(self, rule: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        params = rule['params']
        value = data.get(params['field'])
        if isinstance(value, (int, float)):
            if 'min' in params and value > params['min']:
                return {
                    'status': 'triggered',
                    'message': f"Value exceeds threshold: {value} > {params['min']}",
                }
            if 'max' in params and value < params['max']:
                return {
                    'status': 'triggered',
                    'message': f"Value below threshold: {value} < {params['max']}",
                }
        return {'status': 'not_triggered'}

    def _evaluate_string_match(self, rule: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        params = rule['params']
        value = data.get(params['field'])
        pattern = params['pattern']
        if isinstance(value, str) and pattern in value:
            return {
                'status': 'triggered',
                'message': f"Pattern matched in field: {params['field']}",
            }
        return {'status': 'not_triggered'}


class SafeMathEvaluator:
    """Evaluates simple math expressions using a whitelist of operations."""

    _OPERATIONS = {
        'add': lambda a, b: a + b,
        'sub': lambda a, b: a - b,
        'mul': lambda a, b: a * b,
        'div': lambda a, b: a / b,
        'pow': lambda a, b: a ** b,
        'sqrt': math.sqrt,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'log': math.log,
        'log10': math.log10,
    }

    @staticmethod
    def evaluate(expression: str) -> float:
        try:
            tokens = expression.split()
            if len(tokens) not in (2, 3):
                raise ValueError('Invalid expression format')
            op_name, *operands = tokens
            op = SafeMathEvaluator._OPERATIONS.get(op_name)
            if op is None:
                raise ValueError(f'Invalid operation: {op_name}')
            return op(*[float(operand) for operand in operands])
        except ValueError as e:
            raise ValueError(f'Math evaluation error: {str(e)}')


rule_engine = SafeRuleEngine()
math_evaluator = SafeMathEvaluator()


@app.route('/api/rules/evaluate', methods=['POST'])
def evaluate_rules():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        results = {}
        for rule_name in rule_engine.rules:
            try:
                results[rule_name] = rule_engine.evaluate_rule(rule_name, data)
            except ValueError as e:
                results[rule_name] = {'error': str(e)}
        return jsonify(results)
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/rules/math', methods=['POST'])
def evaluate_math():
    try:
        data = request.get_json()
        if 'expression' not in data:
            return jsonify({'error': 'Expression required'}), 400
        result = math_evaluator.evaluate(data['expression'])
        return jsonify({'result': result})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=False)
