from flask import Flask, request, jsonify
import json
import yaml
import datetime
from uuid import uuid4
from enum import Enum
from typing import Dict, List, Any

_DEFAULT_STEP_TYPE = 'action'
_DEFAULT_STEP_NAME = 'unnamed'

_STATUS_SUCCESS = 'success'
_STATUS_ERROR = 'error'
_STATUS_COMPLETED = 'completed'
_STATUS_FAILED = 'failed'

_ERROR_WORKFLOW_NAME_REQUIRED = 'Workflow name required'
_ERROR_INTERNAL_SERVER = 'Internal server error'

_DATA_PROCESSING_WORKFLOW_NAME = 'data_processing'
_RUN_DEBUG = False

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


class WorkflowEngine:

    def __init__(self):
        self.workflows = {}
        self.safe_functions = {'uuid4': uuid4, 'datetime': datetime.datetime}

    def register_workflow(self, name: str, steps: List[Dict]) -> None:
        self.workflows[name] = [self._validate_step(step) for step in steps]

    def _validate_step(self, step: Dict) -> Dict:
        if not isinstance(step, dict):
            raise ValueError('Each step must be a dictionary')

        step_type = StepType(step.get('type', _DEFAULT_STEP_TYPE))
        validated_step = {'type': step_type.value}

        if step_type == StepType.ACTION:
            self._validate_action_step(step, validated_step)
        elif step_type == StepType.CONDITION:
            self._validate_condition_step(step, validated_step)

        validated_step['name'] = step.get('name', _DEFAULT_STEP_NAME)
        return validated_step

    @staticmethod
    def _validate_action_step(step: Dict, validated_step: Dict) -> None:
        action = ActionType(step['action'])
        validated_step['action'] = action.value
        validated_step['params'] = step.get('params', {})

    @staticmethod
    def _validate_condition_step(step: Dict, validated_step: Dict) -> None:
        operator = ConditionOperator(step['operator'])
        validated_step['field'] = step['field']
        validated_step['operator'] = operator.value
        validated_step['value'] = step['value']

    def _execute_action(self, action: str, params: Dict, context: Dict) -> Dict:
        try:
            action_type = ActionType(action)

            if action_type == ActionType.JSON_LOAD:
                self._set_output(params, context, json.loads(context[params['input']]))
            elif action_type == ActionType.JSON_DUMP:
                self._set_output(params, context, json.dumps(context[params['input']]))
            elif action_type == ActionType.YAML_DUMP:
                self._set_output(params, context, yaml.dump(context[params['input']]))
            elif action_type == ActionType.STR_UPPER:
                self._set_output(params, context, str(context[params['input']]).upper())
            elif action_type == ActionType.STR_LOWER:
                self._set_output(params, context, str(context[params['input']]).lower())
            elif action_type == ActionType.LIST_MAP:
                self._execute_list_map(params, context)

            return {'status': _STATUS_SUCCESS}
        except Exception as e:
            return {'status': _STATUS_ERROR, 'message': str(e)}

    @staticmethod
    def _set_output(params: Dict, context: Dict, value: Any) -> None:
        context[params['output']] = value

    def _execute_list_map(self, params: Dict, context: Dict) -> None:
        func = ActionType(params['func'])
        items = context[params['input']]

        if func == ActionType.STR_UPPER:
            mapped_items = [str(item).upper() for item in items]
        else:
            mapped_items = [str(item).lower() for item in items]

        self._set_output(params, context, mapped_items)

    def _evaluate_condition(self, field: str, operator: str, value: Any, context: Dict) -> Dict:
        try:
            field_value = context.get(field)
            op = ConditionOperator(operator)
            result = self._compare_values(field_value, op, value)
            return {'status': _STATUS_SUCCESS, 'result': result}
        except Exception as e:
            return {'status': _STATUS_ERROR, 'message': str(e)}

    @staticmethod
    def _compare_values(field_value: Any, operator: ConditionOperator, value: Any) -> Any:
        if operator == ConditionOperator.EQUAL:
            return field_value == value
        if operator == ConditionOperator.NOT_EQUAL:
            return field_value != value
        if operator == ConditionOperator.GREATER:
            return field_value > value
        if operator == ConditionOperator.LESS:
            return field_value < value
        if operator == ConditionOperator.GREATER_EQUAL:
            return field_value >= value
        if operator == ConditionOperator.LESS_EQUAL:
            return field_value <= value
        if operator == ConditionOperator.CONTAINS:
            return str(value) in str(field_value)
        if operator == ConditionOperator.STARTS_WITH:
            return str(field_value).startswith(str(value))
        if operator == ConditionOperator.ENDS_WITH:
            return str(field_value).endswith(str(value))
        raise ValueError(f'Unsupported condition operator: {operator}')

    def execute_workflow(self, name: str, initial_context: Dict = None) -> Dict:
        if name not in self.workflows:
            return {'error': f'Workflow {name} not found'}

        context = initial_context or {}
        execution_log = []

        for step in self.workflows[name]:
            step_result = self._execute_step(step, context)
            execution_log.append({'step': step['name'], 'result': step_result})
            if step_result['status'] == _STATUS_ERROR:
                break

        return {
            'workflow': name,
            'status': _STATUS_COMPLETED if execution_log[-1]['status'] == _STATUS_SUCCESS else _STATUS_FAILED,
            'context': context,
            'execution_log': execution_log,
        }

    def _execute_step(self, step: Dict, context: Dict) -> Dict:
        step_type = StepType(step['type'])
        step_result = None

        if step_type == StepType.ACTION:
            step_result = self._execute_action(step['action'], step.get('params', {}), context)
        elif step_type == StepType.CONDITION:
            step_result = self._evaluate_condition(step['field'], step['operator'], step['value'], context)

        return step_result


def _data_processing_workflow_steps() -> List[Dict]:
    return [
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
    ]


workflow_engine = WorkflowEngine()
workflow_engine.register_workflow(_DATA_PROCESSING_WORKFLOW_NAME, _data_processing_workflow_steps())


@app.route('/api/workflows/execute', methods=['POST'])
def execute_workflow():
    data = request.get_json()
    if not data or 'workflow' not in data:
        return (jsonify({'error': _ERROR_WORKFLOW_NAME_REQUIRED}), 400)

    try:
        result = workflow_engine.execute_workflow(data['workflow'], data.get('context', {}))
        return jsonify(result)
    except ValueError as e:
        return (jsonify({'error': str(e)}), 400)
    except Exception:
        return (jsonify({'error': _ERROR_INTERNAL_SERVER}), 500)


if __name__ == '__main__':
    app.run(debug=_RUN_DEBUG)
