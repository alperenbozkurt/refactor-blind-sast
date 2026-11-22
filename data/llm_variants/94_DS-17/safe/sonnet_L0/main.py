import json
import math
import operator
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

from flask import Flask, request, jsonify

app = Flask(__name__)


class RuleType(Enum):
    COMPARISON = 'comparison'
    RANGE_CHECK = 'range_check'
    STRING_MATCH = 'string_match'


_COMPARISON_OPERATORS: Dict[str, Callable[[Any, Any], bool]] = {
    '==': operator.eq,
    '!=': operator.ne,
    '>': operator.gt,
    '<': operator.lt,
    '>=': operator.ge,
    '<=': operator.le,
}

_MATH_OPERATIONS: Dict[str, Callable[..., float]] = {
    'add': operator.add,
    'sub': operator.sub,
    'mul': operator.mul,
    'div': operator.truediv,
    'pow': operator.pow,
    'sqrt': math.sqrt,
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'log': math.log,
    'log10': math.log10,
}


def _triggered(message: str) -> Dict[str, Any]:
    return {'status': 'triggered', 'message': message}


class SafeRuleEngine:

    def __init__(self):
        self.rules: Dict[str, Dict] = {}
        self.load_default_rules()

    def add_rule(self, name: str, rule_type: RuleType, params: Dict[str, Any]) -> None:
        if not isinstance(params, dict):
            raise ValueError('Rule params must be a dictionary')
        self.rules[name] = {'type': rule_type, 'params': params}

    def load_default_rules(self) -> None:
        self.add_rule('high_value_transaction', RuleType.RANGE_CHECK,
                      {'field': 'amount', 'min': 10000})
        self.add_rule('suspicious_login', RuleType.COMPARISON,
                      {'field1': 'login_location', 'field2': 'usual_location', 'operator': '!='})

    @staticmethod
    def _evaluate_comparison(params: Dict[str, Any], data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        val1 = data.get(params['field1'])
        val2 = data.get(params['field2'])
        op = params['operator']
        compare = _COMPARISON_OPERATORS.get(op)
        if compare is None:
            raise ValueError(f'Invalid operator: {op}')
        if compare(val1, val2):
            return _triggered(f"Condition met: {params['field1']} {op} {params['field2']}")
        return None

    @staticmethod
    def _evaluate_range_check(params: Dict[str, Any], data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        value = data.get(params['field'])
        if isinstance(value, (int, float)):
            if 'min' in params and value > params['min']:
                return _triggered(f"Value exceeds threshold: {value} > {params['min']}")
            if 'max' in params and value < params['max']:
                return _triggered(f"Value below threshold: {value} < {params['max']}")
        return None

    @staticmethod
    def _evaluate_string_match(params: Dict[str, Any], data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        value = data.get(params['field'])
        pattern = params['pattern']
        if isinstance(value, str) and pattern in value:
            return _triggered(f"Pattern matched in field: {params['field']}")
        return None

    def evaluate_rule(self, name: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        if name not in self.rules:
            raise ValueError(f"Rule '{name}' not found")
        rule = self.rules[name]
        data = data or {}
        handlers = {
            RuleType.COMPARISON: self._evaluate_comparison,
            RuleType.RANGE_CHECK: self._evaluate_range_check,
            RuleType.STRING_MATCH: self._evaluate_string_match,
        }
        try:
            handler = handlers.get(rule['type'])
            result = handler(rule['params'], data) if handler else None
            return result if result is not None else {'status': 'not_triggered'}
        except Exception as e:
            raise ValueError(f'Rule evaluation error: {str(e)}')


class SafeMathEvaluator:

    @staticmethod
    def evaluate(expression: str) -> float:
        try:
            tokens = expression.split()
            if len(tokens) not in (2, 3):
                raise ValueError('Invalid expression format')
            op_name = tokens[0]
            op = _MATH_OPERATIONS.get(op_name)
            if not op:
                raise ValueError(f'Invalid operation: {op_name}')
            return op(*(float(token) for token in tokens[1:]))
        except ValueError as e:
            raise ValueError(f'Math evaluation error: {str(e)}')


rule_engine = SafeRuleEngine()
math_evaluator = SafeMathEvaluator()


@app.route('/api/rules/evaluate', methods=['POST'])
def evaluate_rules():
    try:
        data = request.get_json()
        if not data:
            return (jsonify({'error': 'No data provided'}), 400)
        results = {}
        for rule_name in rule_engine.rules:
            try:
                results[rule_name] = rule_engine.evaluate_rule(rule_name, data)
            except ValueError as e:
                results[rule_name] = {'error': str(e)}
        return jsonify(results)
    except Exception:
        return (jsonify({'error': 'Internal server error'}), 500)


@app.route('/api/rules/math', methods=['POST'])
def evaluate_math():
    try:
        data = request.get_json()
        if 'expression' not in data:
            return (jsonify({'error': 'Expression required'}), 400)
        result = math_evaluator.evaluate(data['expression'])
        return jsonify({'result': result})
    except ValueError as e:
        return (jsonify({'error': str(e)}), 400)
    except Exception:
        return (jsonify({'error': 'Internal server error'}), 500)


if __name__ == '__main__':
    app.run(debug=False)
