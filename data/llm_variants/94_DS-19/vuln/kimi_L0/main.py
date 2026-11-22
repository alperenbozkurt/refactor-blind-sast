import datetime
import json
from uuid import uuid4

import yaml
from flask import Flask, jsonify, request

app = Flask(__name__)


class WorkflowEngine:
    """Executes named, ordered lists of steps against a shared context."""

    DEFAULT_STEP_TYPE = 'action'
    STATUS_SUCCESS = 'success'
    STATUS_ERROR = 'error'

    def __init__(self):
        self.workflows = {}
        self.execution_context = {
            'datetime': datetime,
            'uuid4': uuid4,
            'json': json,
            'yaml': yaml,
        }

    def register_workflow(self, name, steps):
        self.workflows[name] = steps

    def execute_workflow(self, name, initial_context=None):
        if name not in self.workflows:
            return {'error': f'Workflow {name} not found'}

        context = initial_context or {}
        execution_log = []
        for step in self.workflows[name]:
            step_result = self._execute_step(step, context)
            execution_log.append({
                'step': step.get('name', 'unnamed'),
                'result': step_result,
            })
            if step_result['status'] == self.STATUS_ERROR:
                break

        return {
            'workflow': name,
            'status': ('completed'
                       if execution_log[-1]['status'] == self.STATUS_SUCCESS
                       else 'failed'),
            'context': context,
            'execution_log': execution_log,
        }

    def _execute_step(self, step, context):
        step_type = step.get('type', self.DEFAULT_STEP_TYPE)
        if step_type == 'action':
            return self._execute_action(step, context)
        if step_type == 'condition':
            return self._execute_condition(step, context)
        return {'status': self.STATUS_SUCCESS}

    def _execute_action(self, step, context):
        try:
            exec(step['code'], self.execution_context, context)
        except Exception as e:
            return self._error_result(str(e))
        return {'status': self.STATUS_SUCCESS}

    def _execute_condition(self, step, context):
        try:
            result = eval(step['expression'], self.execution_context, context)
        except Exception as e:
            return self._error_result(str(e))
        return {'status': self.STATUS_SUCCESS, 'result': result}

    @classmethod
    def _error_result(cls, message):
        return {'status': cls.STATUS_ERROR, 'message': message}


workflow_engine = WorkflowEngine()
workflow_engine.register_workflow(
    'data_processing',
    [
        {
            'name': 'load_data',
            'type': 'action',
            'code': 'context["raw_data"] = json.loads(context["input_data"])',
        },
        {
            'name': 'transform',
            'type': 'action',
            'code': 'context["processed"] = [x.upper() for x in context["raw_data"]]',
        },
        {
            'name': 'save',
            'type': 'action',
            'code': 'context["output"] = yaml.dump(context["processed"])',
        },
    ],
)


def _json_payload_or_error(field, error_message):
    """Return ``(payload, None)`` or ``(None, (response, status))``."""
    data = request.get_json()
    if not data or field not in data:
        return None, (jsonify({'error': error_message}), 400)
    return data, None


@app.route('/api/workflows/execute', methods=['POST'])
def execute_workflow():
    data, error = _json_payload_or_error('workflow', 'Workflow name required')
    if error is not None:
        return error
    try:
        result = workflow_engine.execute_workflow(data['workflow'],
                                                  data.get('context', {}))
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflows/custom', methods=['POST'])
def execute_custom_workflow():
    data, error = _json_payload_or_error('steps', 'Steps data required')
    if error is not None:
        return error
    try:
        workflow_name = f'temp_{datetime.datetime.now().timestamp()}'
        workflow_engine.register_workflow(workflow_name, data['steps'])
        result = workflow_engine.execute_workflow(workflow_name,
                                                  data.get('context', {}))
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/expressions/evaluate', methods=['POST'])
def evaluate_expression():
    data, error = _json_payload_or_error('expression', 'Expression required')
    if error is not None:
        return error
    try:
        result = eval(
            data['expression'],
            workflow_engine.execution_context,
            data.get('context', {}),
        )
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True)
