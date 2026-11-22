import json
from flask import Flask, request, jsonify
from datetime import datetime
import math
import operator
from enum import Enum
from typing import Dict, Any, Callable, Optional

app = Flask(__name__)

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

STATUS_TRIGGERED = 'triggered'
STATUS_NOT_TRIGGERED = 'not_triggered'

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

ERROR_NO_DATA = 'No data provided'
ERROR_EXPRESSION_REQUIRED = 'Expression required'
ERROR_INTERNAL = 'Internal server error'

COMPARISON_OPERATORS: Dict[str, Callable[[Any, Any], bool]] = {
    '==': operator.eq,
    '!=': operator.ne,
    '>': operator.gt,
    '<': operator.lt,
    '>=': operator.ge,
    '<=': operator.le,
}

BINARY_MATH_OPERATIONS: Dict[str, Callable[[float, float], float]] = {
    'add': operator.add,
    'sub': operator.sub,
    'mul': operator.mul,
    'div': operator.truediv,
    'pow': operator.pow,
}

UNARY_MATH_OPERATIONS: Dict[str, Callable[[float], float]] = {
    'sqrt': math.sqrt,
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'log': math.log,
    'log10': math.log10,
}

# Combined lookup: names are unique across both groups, and the original
# implementation allowed any operation name with either token count.
ALLOWED_MATH_OPERATIONS: Dict[str, Callable[..., float]] = {
    **BINARY_MATH_OPERATIONS,
    **UNARY_MATH_OPERATIONS,
}

UNARY_TOKEN_COUNT = 2
BINARY_TOKEN_COUNT = 3


class RuleType(Enum):
    COMPARISON = 'comparison'
    RANGE_CHECK = 'range_check'
    STRING_MATCH = 'string_match'


# --------------------------------------------------------------------------
# Rule evaluation helpers
# --------------------------------------------------------------------------

def _triggered(message: str) -> Dict[str, Any]:
    return {'status': STATUS_TRIGGERED, 'message': message}


def _not_triggered() -> Dict[str, Any]:
    return {'status': STATUS_NOT_TRIGGERED}


def _evaluate_comparison(params: Dict[str, Any], data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    val1 = data.get(params['field1'])
    val2 = data.get(params['field2'])
    op = params['operator']
    compare = COMPARISON_OPERATORS.get(op)
    if compare is None:
        raise ValueError(f'Invalid operator: {op}')
    if compare(val1, val2):
        return _triggered(f"Condition met: {params['field1']} {op} {params['field2']}")
    return None


def _evaluate_range_check(params: Dict[str, Any], data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    value = data.get(params['field'])
    if isinstance(value, (int, float)):
        if 'min' in params and value > params['min']:
            return _triggered(f"Value exceeds threshold: {value} > {params['min']}")
        if 'max' in params and value < params['max']:
            return _triggered(f"Value below threshold: {value} < {params['max']}")
    return None


def _evaluate_string_match(params: Dict[str, Any], data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    value = data.get(params['field'])
    pattern = params['pattern']
    if isinstance(value, str) and pattern in value:
        return _triggered(f"Pattern matched in field: {params['field']}")
    return None


RULE_EVALUATORS: Dict[RuleType, Callable[[Dict[str, Any], Dict[str, Any]], Optional[Dict[str, Any]]]] = {
    RuleType.COMPARISON: _evaluate_comparison,
    RuleType.RANGE_CHECK: _evaluate_range_check,
    RuleType.STRING_MATCH: _evaluate_string_match,
}


class SafeRuleEngine:

    def __init__(self):
        self.rules: Dict[str, Dict] = {}
        self.load_default_rules()

    def add_rule(self, name: str, rule_type: RuleType, params: Dict[str, Any]) -> None:
        if not isinstance(params, dict):
            raise ValueError('Rule params must be a dictionary')
        self.rules[name] = {'type': rule_type, 'params': params}

    def load_default_rules(self) -> None:
        self.add_rule('high_value_transaction', RuleType.RANGE_CHECK, {'field': 'amount', 'min': 10000})
        self.add_rule('suspicious_login', RuleType.COMPARISON, {'field1': 'login_location', 'field2': 'usual_location', 'operator': '!='})

    def evaluate_rule(self, name: str, data: Dict[str, Any]=None) -> Dict[str, Any]:
        if name not in self.rules:
            raise ValueError(f"Rule '{name}' not found")
        rule = self.rules[name]
        data = data or {}
        try:
            evaluator = RULE_EVALUATORS.get(rule['type'])
            if evaluator is not None:
                result = evaluator(rule['params'], data)
                if result is not None:
                    return result
            return _not_triggered()
        except Exception as e:
            raise ValueError(f'Rule evaluation error: {str(e)}')


class SafeMathEvaluator:

    @staticmethod
    def _lookup_operation(op_name: str) -> Callable[..., float]:
        op = ALLOWED_MATH_OPERATIONS.get(op_name)
        if not op:
            raise ValueError(f'Invalid operation: {op_name}')
        return op

    @staticmethod
    def evaluate(expression: str) -> float:
        try:
            tokens = expression.split()
            if len(tokens) not in (UNARY_TOKEN_COUNT, BINARY_TOKEN_COUNT):
                raise ValueError('Invalid expression format')
            if len(tokens) == BINARY_TOKEN_COUNT:
                (op_name, a, b) = tokens
                op = SafeMathEvaluator._lookup_operation(op_name)
                return op(float(a), float(b))
            (op_name, a) = tokens
            op = SafeMathEvaluator._lookup_operation(op_name)
            return op(float(a))
        except ValueError as e:
            raise ValueError(f'Math evaluation error: {str(e)}')


rule_engine = SafeRuleEngine()
math_evaluator = SafeMathEvaluator()


def _error_response(message: str, status_code: int):
    return (jsonify({'error': message}), status_code)


@app.route('/api/rules/evaluate', methods=['POST'])
def evaluate_rules():
    try:
        data = request.get_json()
        if not data:
            return _error_response(ERROR_NO_DATA, HTTP_BAD_REQUEST)
        results = {}
        for rule_name in rule_engine.rules:
            try:
                results[rule_name] = rule_engine.evaluate_rule(rule_name, data)
            except ValueError as e:
                results[rule_name] = {'error': str(e)}
        return jsonify(results)
    except Exception as e:
        return _error_response(ERROR_INTERNAL, HTTP_INTERNAL_SERVER_ERROR)


@app.route('/api/rules/math', methods=['POST'])
def evaluate_math():
    try:
        data = request.get_json()
        if 'expression' not in data:
            return _error_response(ERROR_EXPRESSION_REQUIRED, HTTP_BAD_REQUEST)
        result = math_evaluator.evaluate(data['expression'])
        return jsonify({'result': result})
    except ValueError as e:
        return _error_response(str(e), HTTP_BAD_REQUEST)
    except Exception:
        return _error_response(ERROR_INTERNAL, HTTP_INTERNAL_SERVER_ERROR)


if __name__ == '__main__':
    app.run(debug=False)
