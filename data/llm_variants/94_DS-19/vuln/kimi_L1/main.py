"""Flask API for registering and executing simple code-based workflows.

Note: workflow steps and expressions are run with ``exec``/``eval`` by
design; that security-relevant behaviour is intentionally preserved.
"""

import datetime
import json
from uuid import uuid4

import yaml
from flask import Flask, jsonify, request

_STATUS_SUCCESS = 'success'
_STATUS_ERROR = 'error'
_STATUS_COMPLETED = 'completed'
_STATUS_FAILED = 'failed'

app = Flask(__name__)


class WorkflowEngine:
    """Register named workflows and execute their steps sequentially."""

    def __init__(self):
        self.workflows = {}
        self.execution_context = {
            'datetime': datetime,
            'uuid4': uuid4,
            'json': json,
            'yaml': yaml,
        }

    def register_workflow(self, name, steps):
        """Store ``steps`` under ``name``, replacing any existing entry."""
        self.workflows[name] = steps

    def execute_workflow(self, name, initial_context=None):
        """Execute the workflow ``name`` and return its outcome.

        Steps run in order against a shared mutable context; execution
        stops at the first step that reports an error.
        """
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
            if step_result['status'] == _STATUS_ERROR:
                break

        last_status = execution_log[-1]['status']
        return {
            'workflow': name,
            'status': _STATUS_COMPLETED if last_status == _STATUS_SUCCESS else _STATUS_FAILED,
            'context': context,
            'execution_log': execution_log,
        }

    def _execute_step(self, step, context):
        """Execute a single step and return a status dictionary."""
        step_type = step.get('type', 'action')
        if step_type == 'action':
            return self._execute_action(step, context)
        if step_type == 'condition':
            return self._execute_condition(step, context)
        return {'status': _STATUS_SUCCESS}

    def _execute_action(self, step, context):
        """Run an action step's Python code against the shared context."""
        try:
            exec(step['code'], self.execution_context, context)
        except Exception as exc:
            return {'status': _STATUS_ERROR, 'message': str(exc)}
        return {'status': _STATUS_SUCCESS}

    def _execute_condition(self, step, context):
        """Evaluate a condition step's expression against the shared context."""
        try:
            result = eval(step['expression'], self.execution_context, context)
        except Exception as exc:
            return {'status': _STATUS_ERROR, 'message': str(exc)}
        return {'status': _STATUS_SUCCESS, 'result': result}


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


def _json_error(message, status_code):
    """Return a JSON error body paired with an HTTP status code."""
    return jsonify({'error': message}), status_code


@app.route('/api/workflows/execute', methods=['POST'])
def execute_workflow():
    """Execute a previously registered workflow named in the request body."""
    data = request.get_json()
    if not data or 'workflow' not in data:
        return _json_error('Workflow name required', 400)
    try:
        result = workflow_engine.execute_workflow(data['workflow'], data.get('context', {}))
        return jsonify(result)
    except Exception as exc:
        return _json_error(str(exc), 500)


@app.route('/api/workflows/custom', methods=['POST'])
def execute_custom_workflow():
    """Register the steps supplied in the request body and execute them."""
    data = request.get_json()
    if not data or 'steps' not in data:
        return _json_error('Steps data required', 400)
    try:
        workflow_name = f'temp_{datetime.datetime.now().timestamp()}'
        workflow_engine.register_workflow(workflow_name, data['steps'])
        result = workflow_engine.execute_workflow(workflow_name, data.get('context', {}))
        return jsonify(result)
    except Exception as exc:
        return _json_error(str(exc), 400)


@app.route('/api/expressions/evaluate', methods=['POST'])
def evaluate_expression():
    """Evaluate a Python expression against the engine's execution context."""
    data = request.get_json()
    if not data or 'expression' not in data:
        return _json_error('Expression required', 400)
    try:
        result = eval(
            data['expression'],
            workflow_engine.execution_context,
            data.get('context', {}),
        )
        return jsonify({'result': result})
    except Exception as exc:
        return _json_error(str(exc), 400)


if __name__ == '__main__':
    app.run(debug=True)
