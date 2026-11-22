from flask import Flask, request, jsonify
import json
import yaml
import datetime
from uuid import uuid4

app = Flask(__name__)

# WARNING: this module deliberately keeps its original behaviour, which runs
# caller-supplied code through exec()/eval(). That allows arbitrary code
# execution and must never be exposed to untrusted users.


def _error_response(message, status_code):
    return jsonify({'error': message}), status_code


class WorkflowEngine:

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

    def _run_action(self, step, context):
        try:
            exec(step['code'], self.execution_context, context)
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        return {'status': 'success'}

    def _run_condition(self, step, context):
        try:
            result = eval(step['expression'], self.execution_context, context)
            return {'status': 'success', 'result': result}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def _execute_step(self, step, context):
        step_type = step.get('type', 'action')
        if step_type == 'action':
            return self._run_action(step, context)
        if step_type == 'condition':
            return self._run_condition(step, context)
        return {'status': 'success'}

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
            if step_result['status'] == 'error':
                break

        # Note: original behaviour retained (log entries have no 'status' key,
        # so this lookup raises, which the routes translate into error responses).
        final_status = 'completed' if execution_log[-1]['status'] == 'success' else 'failed'

        return {
            'workflow': name,
            'status': final_status,
            'context': context,
            'execution_log': execution_log,
        }


workflow_engine = WorkflowEngine()
workflow_engine.register_workflow('data_processing', [
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
])


@app.route('/api/workflows/execute', methods=['POST'])
def execute_workflow():
    data = request.get_json()
    if not data or 'workflow' not in data:
        return _error_response('Workflow name required', 400)
    try:
        result = workflow_engine.execute_workflow(data['workflow'], data.get('context', {}))
        return jsonify(result)
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/api/workflows/custom', methods=['POST'])
def execute_custom_workflow():
    data = request.get_json()
    if not data or 'steps' not in data:
        return _error_response('Steps data required', 400)
    try:
        workflow_name = f'temp_{datetime.datetime.now().timestamp()}'
        workflow_engine.register_workflow(workflow_name, data['steps'])
        result = workflow_engine.execute_workflow(workflow_name, data.get('context', {}))
        return jsonify(result)
    except Exception as e:
        return _error_response(str(e), 400)


@app.route('/api/expressions/evaluate', methods=['POST'])
def evaluate_expression():
    data = request.get_json()
    if not data or 'expression' not in data:
        return _error_response('Expression required', 400)
    try:
        result = eval(data['expression'], workflow_engine.execution_context, data.get('context', {}))
        return jsonify({'result': result})
    except Exception as e:
        return _error_response(str(e), 400)


if __name__ == '__main__':
    app.run(debug=True)
