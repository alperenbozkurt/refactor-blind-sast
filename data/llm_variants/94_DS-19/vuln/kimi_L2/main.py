"""Flask web service for registering and executing simple workflows.

Exposes three HTTP endpoints:

* ``POST /api/workflows/execute``    -- run a previously registered workflow.
* ``POST /api/workflows/custom``     -- register and run an ad-hoc workflow.
* ``POST /api/expressions/evaluate`` -- evaluate an expression in the shared
  execution context.

Running the module directly starts the Flask development server in debug
mode.
"""

import datetime
import json
from uuid import uuid4

import yaml
from flask import Flask, jsonify, request


class Config:
    """Central configuration: routes, statuses, field names and messages."""

    # Server configuration.
    DEBUG = True

    # HTTP status codes.
    HTTP_BAD_REQUEST = 400
    HTTP_INTERNAL_SERVER_ERROR = 500

    # Routes.
    ROUTE_EXECUTE_WORKFLOW = '/api/workflows/execute'
    ROUTE_EXECUTE_CUSTOM_WORKFLOW = '/api/workflows/custom'
    ROUTE_EVALUATE_EXPRESSION = '/api/expressions/evaluate'

    # Workflow step types.
    STEP_TYPE_ACTION = 'action'
    STEP_TYPE_CONDITION = 'condition'
    DEFAULT_STEP_TYPE = STEP_TYPE_ACTION
    DEFAULT_STEP_NAME = 'unnamed'

    # Step and workflow result statuses.
    STATUS_SUCCESS = 'success'
    STATUS_ERROR = 'error'
    WORKFLOW_COMPLETED = 'completed'
    WORKFLOW_FAILED = 'failed'

    # Request payload fields.
    FIELD_WORKFLOW = 'workflow'
    FIELD_STEPS = 'steps'
    FIELD_CONTEXT = 'context'
    FIELD_EXPRESSION = 'expression'

    # Error messages.
    ERROR_WORKFLOW_NAME_REQUIRED = 'Workflow name required'
    ERROR_STEPS_DATA_REQUIRED = 'Steps data required'
    ERROR_EXPRESSION_REQUIRED = 'Expression required'

    # Naming for ad-hoc (custom) workflows.
    TEMP_WORKFLOW_PREFIX = 'temp_'


app = Flask(__name__)


# ---------------------------------------------------------------------------
# Result / response helpers
# ---------------------------------------------------------------------------

def _build_execution_context():
    """Return the globals namespace shared by workflow steps/expressions."""
    return {'datetime': datetime, 'uuid4': uuid4, 'json': json, 'yaml': yaml}


def _step_success():
    """Result for a step that completed without a return value."""
    return {'status': Config.STATUS_SUCCESS}


def _condition_success(value):
    """Result for a condition step that evaluated successfully."""
    return {'status': Config.STATUS_SUCCESS, 'result': value}


def _step_error(message):
    """Result for a step that raised an exception."""
    return {'status': Config.STATUS_ERROR, 'message': message}


def _json_error(message, status_code):
    """Build a Flask response tuple carrying an error payload."""
    return (jsonify({'error': message}), status_code)


class WorkflowEngine:
    """Registry and sequential executor for named, step-based workflows."""

    def __init__(self):
        self.workflows = {}
        self.execution_context = _build_execution_context()

    def register_workflow(self, name, steps):
        self.workflows[name] = steps

    def _execute_step(self, step, context):
        step_type = step.get('type', Config.DEFAULT_STEP_TYPE)
        if step_type == Config.STEP_TYPE_ACTION:
            return self._execute_action(step, context)
        if step_type == Config.STEP_TYPE_CONDITION:
            return self._execute_condition(step, context)
        return _step_success()

    def _execute_action(self, step, context):
        try:
            exec(step['code'], self.execution_context, context)
        except Exception as e:
            return _step_error(str(e))
        return _step_success()

    def _execute_condition(self, step, context):
        try:
            result = eval(step['expression'], self.execution_context, context)
            return _condition_success(result)
        except Exception as e:
            return _step_error(str(e))

    def execute_workflow(self, name, initial_context=None):
        if name not in self.workflows:
            return {'error': f'Workflow {name} not found'}
        context = initial_context or {}
        execution_log = []
        for step in self.workflows[name]:
            step_result = self._execute_step(step, context)
            execution_log.append(self._log_entry(step, step_result))
            if step_result['status'] == Config.STATUS_ERROR:
                break
        return {
            'workflow': name,
            'status': self._final_status(execution_log),
            'context': context,
            'execution_log': execution_log,
        }

    @staticmethod
    def _log_entry(step, step_result):
        return {
            'step': step.get('name', Config.DEFAULT_STEP_NAME),
            'result': step_result,
        }

    @staticmethod
    def _final_status(execution_log):
        if execution_log[-1]['status'] == Config.STATUS_SUCCESS:
            return Config.WORKFLOW_COMPLETED
        return Config.WORKFLOW_FAILED


# ---------------------------------------------------------------------------
# Engine instance and built-in workflows
# ---------------------------------------------------------------------------

workflow_engine = WorkflowEngine()

DATA_PROCESSING_WORKFLOW_NAME = 'data_processing'
DATA_PROCESSING_STEPS = [
    {
        'name': 'load_data',
        'type': Config.STEP_TYPE_ACTION,
        'code': 'context["raw_data"] = json.loads(context["input_data"])',
    },
    {
        'name': 'transform',
        'type': Config.STEP_TYPE_ACTION,
        'code': 'context["processed"] = [x.upper() for x in context["raw_data"]]',
    },
    {
        'name': 'save',
        'type': Config.STEP_TYPE_ACTION,
        'code': 'context["output"] = yaml.dump(context["processed"])',
    },
]

workflow_engine.register_workflow(DATA_PROCESSING_WORKFLOW_NAME, DATA_PROCESSING_STEPS)


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

@app.route(Config.ROUTE_EXECUTE_WORKFLOW, methods=['POST'])
def execute_workflow():
    """Execute a previously registered workflow by name."""
    data = request.get_json()
    if not data or Config.FIELD_WORKFLOW not in data:
        return _json_error(Config.ERROR_WORKFLOW_NAME_REQUIRED, Config.HTTP_BAD_REQUEST)
    try:
        result = workflow_engine.execute_workflow(
            data[Config.FIELD_WORKFLOW],
            data.get(Config.FIELD_CONTEXT, {}),
        )
        return jsonify(result)
    except Exception as e:
        return _json_error(str(e), Config.HTTP_INTERNAL_SERVER_ERROR)


@app.route(Config.ROUTE_EXECUTE_CUSTOM_WORKFLOW, methods=['POST'])
def execute_custom_workflow():
    """Register an ad-hoc workflow from the request and execute it."""
    data = request.get_json()
    if not data or Config.FIELD_STEPS not in data:
        return _json_error(Config.ERROR_STEPS_DATA_REQUIRED, Config.HTTP_BAD_REQUEST)
    try:
        workflow_name = f'{Config.TEMP_WORKFLOW_PREFIX}{datetime.datetime.now().timestamp()}'
        workflow_engine.register_workflow(workflow_name, data[Config.FIELD_STEPS])
        result = workflow_engine.execute_workflow(
            workflow_name,
            data.get(Config.FIELD_CONTEXT, {}),
        )
        return jsonify(result)
    except Exception as e:
        return _json_error(str(e), Config.HTTP_BAD_REQUEST)


@app.route(Config.ROUTE_EVALUATE_EXPRESSION, methods=['POST'])
def evaluate_expression():
    """Evaluate an expression against the engine's execution context."""
    data = request.get_json()
    if not data or Config.FIELD_EXPRESSION not in data:
        return _json_error(Config.ERROR_EXPRESSION_REQUIRED, Config.HTTP_BAD_REQUEST)
    try:
        result = eval(
            data[Config.FIELD_EXPRESSION],
            workflow_engine.execution_context,
            data.get(Config.FIELD_CONTEXT, {}),
        )
        return jsonify({'result': result})
    except Exception as e:
        return _json_error(str(e), Config.HTTP_BAD_REQUEST)


if __name__ == '__main__':
    app.run(debug=Config.DEBUG)
