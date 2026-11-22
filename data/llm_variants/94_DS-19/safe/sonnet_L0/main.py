from flask import Flask, request, jsonify
import json
import operator as _op
import yaml
import datetime
from uuid import uuid4
from enum import Enum
from typing import Dict, List, Any

app = Flask(__name__)


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


def _list_map(params: Dict, context: Dict) -> List[str]:
    func = ActionType(params['func'])
    convert = str.upper if func == ActionType.STR_UPPER else str.lower
    return [convert(str(item)) for item in context[params['input']]]


# Each handler computes the output value from (params, context).
_ACTION_HANDLERS = {
    ActionType.JSON_LOAD: lambda params, ctx: json.loads(ctx[params['input']]),
    ActionType.JSON_DUMP: lambda params, ctx: json.dumps(ctx[params['input']]),
    ActionType.YAML_DUMP: lambda params, ctx: yaml.dump(ctx[params['input']]),
    ActionType.STR_UPPER: lambda params, ctx: str(ctx[params['input']]).upper(),
    ActionType.STR_LOWER: lambda params, ctx: str(ctx[params['input']]).lower(),
    ActionType.LIST_MAP: _list_map,
}

_CONDITION_HANDLERS = {
    ConditionOperator.EQUAL: _op.eq,
    ConditionOperator.NOT_EQUAL: _op.ne,
    ConditionOperator.GREATER: _op.gt,
    ConditionOperator.LESS: _op.lt,
    ConditionOperator.GREATER_EQUAL: _op.ge,
    ConditionOperator.LESS_EQUAL: _op.le,
    ConditionOperator.CONTAINS: lambda field_value, value: str(value) in str(field_value),
    ConditionOperator.STARTS_WITH: lambda field_value, value: str(field_value).startswith(str(value)),
    ConditionOperator.ENDS_WITH: lambda field_value, value: str(field_value).endswith(str(value)),
}


class WorkflowEngine:

    def __init__(self):
        self.workflows = {}
        self.safe_functions = {'uuid4': uuid4, 'datetime': datetime.datetime}

    @staticmethod
    def _validate_step(step: Dict) -> Dict:
        if not isinstance(step, dict):
            raise ValueError('Each step must be a dictionary')
        step_type = StepType(step.get('type', 'action'))
        validated_step = {'type': step_type.value}
        if step_type == StepType.ACTION:
            action = ActionType(step['action'])
            validated_step['action'] = action.value
            validated_step['params'] = step.get('params', {})
        elif step_type == StepType.CONDITION:
            operator = ConditionOperator(step['operator'])
            validated_step['field'] = step['field']
            validated_step['operator'] = operator.value
            validated_step['value'] = step['value']
        validated_step['name'] = step.get('name', 'unnamed')
        return validated_step

    def register_workflow(self, name: str, steps: List[Dict]) -> None:
        self.workflows[name] = [self._validate_step(step) for step in steps]

    def _execute_action(self, action: str, params: Dict, context: Dict) -> Dict:
        try:
            handler = _ACTION_HANDLERS[ActionType(action)]
            value = handler(params, context)
            context[params['output']] = value
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def _evaluate_condition(self, field: str, operator: str, value: Any, context: Dict) -> Dict:
        try:
            field_value = context.get(field)
            handler = _CONDITION_HANDLERS[ConditionOperator(operator)]
            result = handler(field_value, value)
            return {'status': 'success', 'result': result}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def execute_workflow(self, name: str, initial_context: Dict=None) -> Dict:
        if name not in self.workflows:
            return {'error': f'Workflow {name} not found'}
        context = initial_context or {}
        execution_log = []
        for step in self.workflows[name]:
            step_type = StepType(step['type'])
            step_result = None
            if step_type == StepType.ACTION:
                step_result = self._execute_action(step['action'], step.get('params', {}), context)
            elif step_type == StepType.CONDITION:
                step_result = self._evaluate_condition(step['field'], step['operator'], step['value'], context)
            execution_log.append({'step': step['name'], 'result': step_result})
            if step_result['status'] == 'error':
                break
        return {
            'workflow': name,
            'status': 'completed' if execution_log[-1]['status'] == 'success' else 'failed',
            'context': context,
            'execution_log': execution_log,
        }


workflow_engine = WorkflowEngine()
workflow_engine.register_workflow('data_processing', [
    {'name': 'load_data', 'type': 'action', 'action': 'json_load',
     'params': {'input': 'input_data', 'output': 'raw_data'}},
    {'name': 'transform', 'type': 'action', 'action': 'list_map',
     'params': {'input': 'raw_data', 'output': 'processed', 'func': 'str_upper'}},
    {'name': 'save', 'type': 'action', 'action': 'yaml_dump',
     'params': {'input': 'processed', 'output': 'output'}},
])


@app.route('/api/workflows/execute', methods=['POST'])
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
