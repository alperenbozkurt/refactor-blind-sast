import json
from flask import Flask, request, jsonify
from datetime import datetime
import math
from enum import Enum
from typing import Dict, Any, Optional as _Optional

app = Flask(__name__)

class RuleType(Enum):
    COMPARISON = 'comparison'
    RANGE_CHECK = 'range_check'
    STRING_MATCH = 'string_match'

_RULE_TYPE_KEY = 'type'
_RULE_PARAMS_KEY = 'params'
_STATUS_KEY = 'status'
_MESSAGE_KEY = 'message'
_ERROR_KEY = 'error'
_RESULT_KEY = 'result'

_STATUS_TRIGGERED = 'triggered'
_STATUS_NOT_TRIGGERED = 'not_triggered'

_FIELD_PARAM = 'field'
_FIELD1_PARAM = 'field1'
_FIELD2_PARAM = 'field2'
_OPERATOR_PARAM = 'operator'
_MIN_PARAM = 'min'
_MAX_PARAM = 'max'
_PATTERN_PARAM = 'pattern'

_OPERATOR_EQUAL = '=='
_OPERATOR_NOT_EQUAL = '!='
_OPERATOR_GREATER_THAN = '>'
_OPERATOR_LESS_THAN = '<'
_OPERATOR_GREATER_THAN_OR_EQUAL = '>='
_OPERATOR_LESS_THAN_OR_EQUAL = '<='

_HIGH_VALUE_TRANSACTION_RULE = 'high_value_transaction'
_SUSPICIOUS_LOGIN_RULE = 'suspicious_login'
_AMOUNT_FIELD = 'amount'
_LOGIN_LOCATION_FIELD = 'login_location'
_USUAL_LOCATION_FIELD = 'usual_location'
_HIGH_VALUE_TRANSACTION_MIN = 10000

class SafeRuleEngine:

    def __init__(self):
        self.rules: Dict[str, Dict] = {}
        self.load_default_rules()

    def add_rule(self, name: str, rule_type: RuleType, params: Dict[str, Any]) -> None:
        if not isinstance(params, dict):
            raise ValueError('Rule params must be a dictionary')
        self.rules[name] = {_RULE_TYPE_KEY: rule_type, _RULE_PARAMS_KEY: params}

    def load_default_rules(self) -> None:
        self.add_rule(
            _HIGH_VALUE_TRANSACTION_RULE,
            RuleType.RANGE_CHECK,
            {_FIELD_PARAM: _AMOUNT_FIELD, _MIN_PARAM: _HIGH_VALUE_TRANSACTION_MIN},
        )
        self.add_rule(
            _SUSPICIOUS_LOGIN_RULE,
            RuleType.COMPARISON,
            {
                _FIELD1_PARAM: _LOGIN_LOCATION_FIELD,
                _FIELD2_PARAM: _USUAL_LOCATION_FIELD,
                _OPERATOR_PARAM: _OPERATOR_NOT_EQUAL,
            },
        )

    def evaluate_rule(self, name: str, data: Dict[str, Any]=None) -> Dict[str, Any]:
        if name not in self.rules:
            raise ValueError(f"Rule '{name}' not found")
        rule = self.rules[name]
        data = data or {}
        try:
            if rule[_RULE_TYPE_KEY] == RuleType.COMPARISON:
                result = self._evaluate_comparison_rule(rule, data)
                if result is not None:
                    return result
            elif rule[_RULE_TYPE_KEY] == RuleType.RANGE_CHECK:
                result = self._evaluate_range_rule(rule, data)
                if result is not None:
                    return result
            elif rule[_RULE_TYPE_KEY] == RuleType.STRING_MATCH:
                result = self._evaluate_string_rule(rule, data)
                if result is not None:
                    return result
            return self._not_triggered_result()
        except Exception as e:
            raise ValueError(f'Rule evaluation error: {str(e)}')

    def _evaluate_comparison_rule(self, rule: Dict[str, Any], data: Dict[str, Any]) -> _Optional[Dict[str, Any]]:
        val1 = data.get(rule[_RULE_PARAMS_KEY][_FIELD1_PARAM])
        val2 = data.get(rule[_RULE_PARAMS_KEY][_FIELD2_PARAM])
        operator = rule[_RULE_PARAMS_KEY][_OPERATOR_PARAM]
        if not self._is_condition_met(val1, val2, operator):
            return None
        return self._triggered_result(
            f"Condition met: {rule[_RULE_PARAMS_KEY][_FIELD1_PARAM]} {operator} {rule[_RULE_PARAMS_KEY][_FIELD2_PARAM]}"
        )

    def _evaluate_range_rule(self, rule: Dict[str, Any], data: Dict[str, Any]) -> _Optional[Dict[str, Any]]:
        value = data.get(rule[_RULE_PARAMS_KEY][_FIELD_PARAM])
        if isinstance(value, (int, float)):
            if _MIN_PARAM in rule[_RULE_PARAMS_KEY] and value > rule[_RULE_PARAMS_KEY][_MIN_PARAM]:
                return self._triggered_result(
                    f"Value exceeds threshold: {value} > {rule[_RULE_PARAMS_KEY][_MIN_PARAM]}"
                )
            if _MAX_PARAM in rule[_RULE_PARAMS_KEY] and value < rule[_RULE_PARAMS_KEY][_MAX_PARAM]:
                return self._triggered_result(
                    f"Value below threshold: {value} < {rule[_RULE_PARAMS_KEY][_MAX_PARAM]}"
                )
        return None

    def _evaluate_string_rule(self, rule: Dict[str, Any], data: Dict[str, Any]) -> _Optional[Dict[str, Any]]:
        value = data.get(rule[_RULE_PARAMS_KEY][_FIELD_PARAM])
        pattern = rule[_RULE_PARAMS_KEY][_PATTERN_PARAM]
        if isinstance(value, str) and pattern in value:
            return self._triggered_result(
                f"Pattern matched in field: {rule[_RULE_PARAMS_KEY][_FIELD_PARAM]}"
            )
        return None

    @staticmethod
    def _is_condition_met(val1: Any, val2: Any, operator: str) -> bool:
        if operator == _OPERATOR_EQUAL:
            return val1 == val2
        if operator == _OPERATOR_NOT_EQUAL:
            return val1 != val2
        if operator == _OPERATOR_GREATER_THAN:
            return val1 > val2
        if operator == _OPERATOR_LESS_THAN:
            return val1 < val2
        if operator == _OPERATOR_GREATER_THAN_OR_EQUAL:
            return val1 >= val2
        if operator == _OPERATOR_LESS_THAN_OR_EQUAL:
            return val1 <= val2
        raise ValueError(f'Invalid operator: {operator}')

    @staticmethod
    def _triggered_result(message: str) -> Dict[str, Any]:
        return {_STATUS_KEY: _STATUS_TRIGGERED, _MESSAGE_KEY: message}

    @staticmethod
    def _not_triggered_result() -> Dict[str, Any]:
        return {_STATUS_KEY: _STATUS_NOT_TRIGGERED}

_BINARY_EXPRESSION_LENGTH = 3
_UNARY_EXPRESSION_LENGTH = 2

def _build_allowed_operations() -> Dict[str, Any]:
    return {
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

def _get_allowed_operation(allowed_operations: Dict[str, Any], operation_name: str) -> Any:
    operation = allowed_operations.get(operation_name)
    if not operation:
        raise ValueError(f'Invalid operation: {operation_name}')
    return operation

class SafeMathEvaluator:

    @staticmethod
    def evaluate(expression: str) -> float:
        allowed_operations = _build_allowed_operations()
        try:
            tokens = expression.split()
            if len(tokens) not in (_BINARY_EXPRESSION_LENGTH, _UNARY_EXPRESSION_LENGTH):
                raise ValueError('Invalid expression format')
            if len(tokens) == _BINARY_EXPRESSION_LENGTH:
                (operation_name, a, b) = tokens
                operation = _get_allowed_operation(allowed_operations, operation_name)
                return operation(float(a), float(b))
            (operation_name, a) = tokens
            operation = _get_allowed_operation(allowed_operations, operation_name)
            return operation(float(a))
        except ValueError as e:
            raise ValueError(f'Math evaluation error: {str(e)}')

rule_engine = SafeRuleEngine()
math_evaluator = SafeMathEvaluator()

_RULES_EVALUATE_ROUTE = '/api/rules/evaluate'
_RULES_MATH_ROUTE = '/api/rules/math'
_POST_METHOD = 'POST'
_BAD_REQUEST_STATUS = 400
_INTERNAL_SERVER_ERROR_STATUS = 500

_EXPRESSION_FIELD = 'expression'
_NO_DATA_PROVIDED_MESSAGE = 'No data provided'
_EXPRESSION_REQUIRED_MESSAGE = 'Expression required'
_INTERNAL_SERVER_ERROR_MESSAGE = 'Internal server error'

def _error_response(message: str, status_code: int) -> Any:
    return (jsonify({_ERROR_KEY: message}), status_code)

@app.route(_RULES_EVALUATE_ROUTE, methods=[_POST_METHOD])
def evaluate_rules():
    try:
        data = request.get_json()
        if not data:
            return _error_response(_NO_DATA_PROVIDED_MESSAGE, _BAD_REQUEST_STATUS)
        results = {}
        for rule_name in rule_engine.rules:
            try:
                results[rule_name] = rule_engine.evaluate_rule(rule_name, data)
            except ValueError as e:
                results[rule_name] = {_ERROR_KEY: str(e)}
        return jsonify(results)
    except Exception:
        return _error_response(_INTERNAL_SERVER_ERROR_MESSAGE, _INTERNAL_SERVER_ERROR_STATUS)

@app.route(_RULES_MATH_ROUTE, methods=[_POST_METHOD])
def evaluate_math():
    try:
        data = request.get_json()
        if _EXPRESSION_FIELD not in data:
            return _error_response(_EXPRESSION_REQUIRED_MESSAGE, _BAD_REQUEST_STATUS)
        result = math_evaluator.evaluate(data[_EXPRESSION_FIELD])
        return jsonify({_RESULT_KEY: result})
    except ValueError as e:
        return _error_response(str(e), _BAD_REQUEST_STATUS)
    except Exception:
        return _error_response(_INTERNAL_SERVER_ERROR_MESSAGE, _INTERNAL_SERVER_ERROR_STATUS)

if __name__ == '__main__':
    app.run(debug=False)
