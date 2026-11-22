from flask import Flask, request, jsonify
import json
import yaml
import datetime
import operator as _op
from uuid import uuid4
from enum import Enum
from typing import Dict, List, Any, Callable

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
STATUS_SUCCESS = 'success'
STATUS_ERROR = 'error'
STATUS_COMPLETED = 'completed'
STATUS_FAILED = 'failed'

DEFAULT_STEP_TYPE = 'action'
DEFAULT_STEP_NAME = 'unnamed'

EXECUTE_ROUTE = '/api/workflows/execute'


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class StepType(Enum):
    ACTION = 'action'
    CONDITION = 'condition'


class ActionType(Enum):
    JSON_LOAD = 'json_load'
    JSON_DUMP = 'json_dump'
    YAML_DUMP = 'yaml_dump'
    STR_UPPER = 'str_upper'
    STR_LOWER = 'str_lower'
    LIST_MAP = 'list_map'


class ConditionOperator(Enum):
    EQUAL = '=='
    NOT_EQUAL = '!='
    GREATER = '>'
    LESS = '<'
    GREATER_EQUAL = '>='
    LESS_EQUAL = '<='
    CONTAINS = 'contains'
    STARTS_WITH = 'starts_with'
    ENDS_WITH = 'ends_with'


# --------------------------------------------------------------------------- #
# Result helpers
# --------------------------------------------------------------------------- #
def _success(**extra: Any) -> Dict:
    return {'status': STATUS_SUCCESS, **extra}


def _error(exc: Exception) -> Dict:
    return {'status': STATUS_ERROR, 'message': str(exc)}


# --------------------------------------------------------------------------- #
# Action handlers
# --------------------------------------------------------------------------- #
def _to_upper(value: Any) -> str:
    return str(value).upper()


def _to_lower(value: Any) -> str:
    return str(value).lower()


def _apply_unary(transform: Callable[[Any], Any], params: Dict, context: Dict) -> None:
    result = transform(context[params['input']])
    context[params['output']] = result


def _action_json_load(params: Dict, context: Dict) -> None:
    _apply_unary(json.loads, params, context)


def _action_json_dump(params: Dict, context: Dict) -> None:
    _apply_unary(json.dumps, params, context)


def _action_yaml_dump(params: Dict, context: Dict) -> None:
    _apply_unary(yaml.dump, params, context)


def _action_str_upper(params: Dict, context: Dict) -> None:
    _apply_unary(_to_upper, params, context)


def _action_str_lower(params: Dict, context: Dict) -> None:
    _apply_unary(_to_lower, params, context)


def _action_list_map(params: Dict, context: Dict) -> None:
    func = ActionType(params['func'])
    item_transform = _to_upper if func == ActionType.STR_UPPER else _to_lower
    result = [item_transform(item) for item in context[params['input']]]
    context[params['output']] = result


ACTION_HANDLERS: Dict[ActionType, Callable[[Dict, Dict], None]] = {
    ActionType.JSON_LOAD: _action_json_load,
    ActionType.JSON_DUMP: _action_json_dump,
    ActionType.YAML_DUMP: _action_yaml_dump,
    ActionType.STR_UPPER: _action_str_upper,
    ActionType.STR_LOWER: _action_str_lower,
    ActionType.LIST_MAP: _action_list_map,
}


# --------------------------------------------------------------------------- #
# Condition evaluators
# --------------------------------------------------------------------------- #
def _contains(field_value: Any, value: Any) -> bool:
    return str(value) in str(field_value)


def _starts_with(field_value: Any, value: Any) -> bool:
    return str(field_value).startswith(str(value))


def _ends_with(field_value: Any, value: Any) -> bool:
    return str(field_value).endswith(str(value))


CONDITION_EVALUATORS: Dict[ConditionOperator, Callable[[Any, Any], Any]] = {
    ConditionOperator.EQUAL: _op.eq,
    ConditionOperator.NOT_EQUAL: _op.ne,
    ConditionOperator.GREATER: _op.gt,
    ConditionOperator.LESS: _op.lt,
    ConditionOperator.GREATER_EQUAL: _op.ge,
    ConditionOperator.LESS_EQUAL: _op.le,
    ConditionOperator.CONTAINS: _contains,
    ConditionOperator.STARTS_WITH: _starts_with,
    ConditionOperator.ENDS_WITH: _ends_with,
}


# --------------------------------------------------------------------------- #
# Step validation
# --------------------------------------------------------------------------- #
def _validate_action_step(step: Dict, validated_step: Dict) -> None:
    action = ActionType(step['action'])
    validated_step['action'] = action.value
    validated_step['params'] = step.get('params', {})


def _validate_condition_step(step: Dict, validated_step: Dict) -> None:
    condition_operator = ConditionOperator(step['operator'])
    validated_step['field'] = step['field']
    validated_step['operator'] = condition_operator.value
    validated_step['value'] = step['value']


STEP_VALIDATORS: Dict[StepType, Callable[[Dict, Dict], None]] = {
    StepType.ACTION: _validate_action_step,
    StepType.CONDITION: _validate_condition_step,
}


def _validate_step(step: Any) -> Dict:
    if not isinstance(step, dict):
        raise ValueError('Each step must be a dictionary')
    step_type = StepType(step.get('type', DEFAULT_STEP_TYPE))
    validated_step = {'type': step_type.value}
    STEP_VALIDATORS[step_type](step, validated_step)
    validated_step['name'] = step.get('name', DEFAULT_STEP_NAME)
    return validated_step


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class WorkflowEngine:

    def __init__(self):
        self.workflows = {}
        self.safe_functions = {'uuid4': uuid4, 'datetime': datetime.datetime}

    def register_workflow(self, name: str, steps: List[Dict]) -> None:
        validated_steps = [_validate_step(step) for step in steps]
        self.workflows[name] = validated_steps

    def _execute_action(self, action: str, params: Dict, context: Dict) -> Dict:
        try:
            action_type = ActionType(action)
            ACTION_HANDLERS[action_type](params, context)
            return _success()
        except Exception as e:
            return _error(e)

    def _evaluate_condition(self, field: str, operator: str, value: Any, context: Dict) -> Dict:
        try:
            field_value = context.get(field)
            op = ConditionOperator(operator)
            result = CONDITION_EVALUATORS[op](field_value, value)
            return _success(result=result)
        except Exception as e:
            return _error(e)

    def _execute_step(self, step: Dict, context: Dict) -> Dict:
        step_type = StepType(step['type'])
        step_result = None
        if step_type == StepType.ACTION:
            step_result = self._execute_action(step['action'], step.get('params', {}), context)
        elif step_type == StepType.CONDITION:
            step_result = self._evaluate_condition(step['field'], step['operator'], step['value'], context)
        return step_result

    def execute_workflow(self, name: str, initial_context: Dict=None) -> Dict:
        if name not in self.workflows:
            return {'error': f'Workflow {name} not found'}
        context = initial_context or {}
        execution_log = []
        for step in self.workflows[name]:
            step_result = self._execute_step(step, context)
            execution_log.append({'step': step['name'], 'result': step_result})
            if step_result['status'] == STATUS_ERROR:
                break
        return {
            'workflow': name,
            'status': STATUS_COMPLETED if execution_log[-1]['status'] == STATUS_SUCCESS else STATUS_FAILED,
            'context': context,
            'execution_log': execution_log,
        }


# --------------------------------------------------------------------------- #
# Default workflows
# --------------------------------------------------------------------------- #
DATA_PROCESSING_STEPS = [
    {'name': 'load_data', 'type': 'action', 'action': 'json_load',
     'params': {'input': 'input_data', 'output': 'raw_data'}},
    {'name': 'transform', 'type': 'action', 'action': 'list_map',
     'params': {'input': 'raw_data', 'output': 'processed', 'func': 'str_upper'}},
    {'name': 'save', 'type': 'action', 'action': 'yaml_dump',
     'params': {'input': 'processed', 'output': 'output'}},
]

workflow_engine = WorkflowEngine()
workflow_engine.register_workflow('data_processing', DATA_PROCESSING_STEPS)


# --------------------------------------------------------------------------- #
# HTTP layer
# --------------------------------------------------------------------------- #
@app.route(EXECUTE_ROUTE, methods=['POST'])
def execute_workflow():
    data = request.get_json()
    if not data or 'workflow' not in data:
        return (jsonify({'error': 'Workflow name required'}), 400)
    try:
        result = workflow_engine.execute_workflow(data['workflow'], data.get('context', {}))
        return jsonify(result)
    except ValueError as e:
        return (jsonify({'error': str(e)}), 400)
    except Exception:
        return (jsonify({'error': 'Internal server error'}), 500)


if __name__ == '__main__':
    app.run(debug=False)
