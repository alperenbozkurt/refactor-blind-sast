import datetime
import json
import operator as py_operator
from enum import Enum
from typing import Any, Callable, Dict, List
from uuid import uuid4

import yaml
from flask import Flask, request, jsonify

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


def _map_list(params: Dict, context: Dict) -> List[str]:
    func = ActionType(params['func'])
    convert = str.upper if func == ActionType.STR_UPPER else str.lower
    return [convert(str(item)) for item in context[params['input']]]


# Each action handler computes the value to store under params['output'].
ACTION_HANDLERS: Dict[ActionType, Callable[[Dict, Dict], Any]] = {
    ActionType.JSON_LOAD: lambda params, context: json.loads(context[params['input']]),
    ActionType.JSON_DUMP: lambda params, context: json.dumps(context[params['input']]),
    ActionType.YAML_DUMP: lambda params, context: yaml.dump(context[params['input']]),
    ActionType.STR_UPPER: lambda params, context: str(context[params['input']]).upper(),
    ActionType.STR_LOWER: lambda params, context: str(context[params['input']]).lower(),
    ActionType.LIST_MAP: _map_list,
}

CONDITION_EVALUATORS: Dict[ConditionOperator, Callable[[Any, Any], bool]] = {
    ConditionOperator.EQUAL: py_operator.eq,
    ConditionOperator.NOT_EQUAL: py_operator.ne,
    ConditionOperator.GREATER: py_operator.gt,
    ConditionOperator.LESS: py_operator.lt,
    ConditionOperator.GREATER_EQUAL: py_operator.ge,
    ConditionOperator.LESS_EQUAL: py_operator.le,
    ConditionOperator.CONTAINS: lambda field_value, value: str(value) in str(field_value),
    ConditionOperator.STARTS_WITH: lambda field_value, value: str(field_value).startswith(str(value)),
    ConditionOperator.ENDS_WITH: lambda field_value, value: str(field_value).endswith(str(value)),
}


class WorkflowEngine:

    def __init__(self):
        self.workflows = {}
        self.safe_functions = {'uuid4': uuid4, 'datetime': datetime.datetime}

    def register_workflow(self, name: str, steps: List[Dict]) -> None:
        self.workflows[name] = [self._validate_step(step) for step in steps]

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
            condition_operator = ConditionOperator(step['operator'])
            validated_step['field'] = step['field']
            validated_step['operator'] = condition_operator.value
            validated_step['value'] = step['value']

        validated_step['name'] = step.get('name', 'unnamed')
        return validated_step

    def _execute_action(self, action: str, params: Dict, context: Dict) -> Dict:
        try:
            action_type = ActionType(action)
            result = ACTION_HANDLERS[action_type](params, context)
            context[params['output']] = result
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def _evaluate_condition(self, field: str, operator: str, value: Any, context: Dict) -> Dict:
        try:
            field_value = context.get(field)
            op = ConditionOperator(operator)
            result = CONDITION_EVALUATORS[op](field_value, value)
            return {'status': 'success', 'result': result}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

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
    {
        'name': 'load_data',
        'type': 'action',
        'action': 'json_load',
        'params': {'input': 'input_data', 'output': 'raw_data'},
    },
    {
        'name': 'transform',
        'type': 'action',
        'action': 'list_map',
        'params': {'input': 'raw_data', 'output': 'processed', 'func': 'str_upper'},
    },
    {
        'name': 'save',
        'type': 'action',
        'action': 'yaml_dump',
        'params': {'input': 'processed', 'output': 'output'},
    },
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
