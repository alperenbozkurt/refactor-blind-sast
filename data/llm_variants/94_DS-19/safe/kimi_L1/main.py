"""Minimal workflow engine exposed over HTTP with Flask.

A workflow is an ordered list of steps. Action steps transform values in a
shared context dictionary, while condition steps evaluate a predicate against
a context field. Execution stops at the first step that reports an error.
"""

import datetime
import json
import operator
from enum import Enum
from typing import Any, Callable, Dict, List
from uuid import uuid4

import yaml
from flask import Flask, jsonify, request

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
    """Store named workflows and execute them against a mutable context."""

    _CONDITION_CHECKS: Dict[ConditionOperator, Callable[[Any, Any], bool]] = {
        ConditionOperator.EQUAL: operator.eq,
        ConditionOperator.NOT_EQUAL: operator.ne,
        ConditionOperator.GREATER: operator.gt,
        ConditionOperator.LESS: operator.lt,
        ConditionOperator.GREATER_EQUAL: operator.ge,
        ConditionOperator.LESS_EQUAL: operator.le,
        ConditionOperator.CONTAINS: lambda field_value, value: str(value) in str(field_value),
        ConditionOperator.STARTS_WITH: lambda field_value, value: str(field_value).startswith(str(value)),
        ConditionOperator.ENDS_WITH: lambda field_value, value: str(field_value).endswith(str(value)),
    }

    def __init__(self):
        self.workflows = {}
        self.safe_functions = {'uuid4': uuid4, 'datetime': datetime.datetime}
        self._action_handlers: Dict[ActionType, Callable[[Dict, Dict], None]] = {
            ActionType.JSON_LOAD: self._apply_json_load,
            ActionType.JSON_DUMP: self._apply_json_dump,
            ActionType.YAML_DUMP: self._apply_yaml_dump,
            ActionType.STR_UPPER: self._apply_str_upper,
            ActionType.STR_LOWER: self._apply_str_lower,
            ActionType.LIST_MAP: self._apply_list_map,
        }

    def register_workflow(self, name: str, steps: List[Dict]) -> None:
        """Validate every step and store the workflow under the given name."""
        self.workflows[name] = [self._validate_step(step) for step in steps]

    @staticmethod
    def _validate_step(step: Dict) -> Dict:
        """Normalize a raw step definition into its stored representation."""
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

    def execute_workflow(self, name: str, initial_context: Dict = None) -> Dict:
        """Run the workflow's steps in order, stopping at the first error."""
        if name not in self.workflows:
            return {'error': f'Workflow {name} not found'}
        context = initial_context or {}
        execution_log = []
        for step in self.workflows[name]:
            step_result = self._execute_step(step, context)
            execution_log.append({'step': step['name'], 'result': step_result})
            if step_result['status'] == 'error':
                break
        workflow_status = 'completed' if execution_log[-1]['status'] == 'success' else 'failed'
        return {
            'workflow': name,
            'status': workflow_status,
            'context': context,
            'execution_log': execution_log,
        }

    def _execute_step(self, step: Dict, context: Dict) -> Dict:
        step_type = StepType(step['type'])
        if step_type == StepType.ACTION:
            return self._execute_action(step['action'], step.get('params', {}), context)
        if step_type == StepType.CONDITION:
            return self._evaluate_condition(step['field'], step['operator'], step['value'], context)

    def _execute_action(self, action: str, params: Dict, context: Dict) -> Dict:
        """Apply an action to the context, capturing any failure as a result."""
        try:
            handler = self._action_handlers[ActionType(action)]
            handler(params, context)
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @staticmethod
    def _apply_json_load(params: Dict, context: Dict) -> None:
        context[params['output']] = json.loads(context[params['input']])

    @staticmethod
    def _apply_json_dump(params: Dict, context: Dict) -> None:
        context[params['output']] = json.dumps(context[params['input']])

    @staticmethod
    def _apply_yaml_dump(params: Dict, context: Dict) -> None:
        context[params['output']] = yaml.dump(context[params['input']])

    @staticmethod
    def _apply_str_upper(params: Dict, context: Dict) -> None:
        context[params['output']] = str(context[params['input']]).upper()

    @staticmethod
    def _apply_str_lower(params: Dict, context: Dict) -> None:
        context[params['output']] = str(context[params['input']]).lower()

    @staticmethod
    def _apply_list_map(params: Dict, context: Dict) -> None:
        func = ActionType(params['func'])
        context[params['output']] = [
            str(item).upper() if func == ActionType.STR_UPPER else str(item).lower()
            for item in context[params['input']]
        ]

    def _evaluate_condition(self, field: str, operator: str, value: Any, context: Dict) -> Dict:
        """Compare a context field with a value, capturing any failure."""
        try:
            field_value = context.get(field)
            check = self._CONDITION_CHECKS[ConditionOperator(operator)]
            result = check(field_value, value)
            return {'status': 'success', 'result': result}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


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
        return jsonify({'error': 'Workflow name required'}), 400
    try:
        result = workflow_engine.execute_workflow(data['workflow'], data.get('context', {}))
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=False)
