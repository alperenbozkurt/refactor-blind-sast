import cherrypy
import json
import time
import os
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any


class OperationType(str, Enum):
    SUM = 'sum'
    AVERAGE = 'average'
    MAX = 'max'
    MIN = 'min'


@dataclass
class WorkflowStep:
    operation: OperationType
    values: list
    filter_condition: str = None


class WorkflowEngine:

    def __init__(self):
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.shared_context = {'timestamp': time.time(), 'last_run': None}

    def execute_step(self, workflow_id: str, step_config: str):
        try:
            step = self._parse_step(step_config)
            filtered_values = self._filter_values(step)
            result = self._run_operation(step.operation, filtered_values)
            self._store_result(workflow_id, result)
            return result
        except json.JSONDecodeError as e:
            return f'Invalid configuration: {str(e)}'
        except ValueError as e:
            return f'Validation error: {str(e)}'
        except Exception as e:
            return f'Execution failed: {str(e)}'

    def _parse_step(self, step_config: str) -> WorkflowStep:
        step_data = json.loads(step_config)
        step = WorkflowStep(
            operation=OperationType(step_data.get('operation')),
            values=step_data.get('values', []),
            filter_condition=step_data.get('filter'),
        )
        if not all(isinstance(x, (int, float)) for x in step.values):
            raise ValueError('All values must be numbers')
        return step

    def _filter_values(self, step: WorkflowStep) -> list:
        if step.filter_condition:
            return [x for x in step.values if self._evaluate_filter(x, step.filter_condition)]
        return step.values

    def _run_operation(self, operation: OperationType, values: list):
        if operation == OperationType.SUM:
            return sum(values)
        elif operation == OperationType.AVERAGE:
            return sum(values) / len(values) if values else 0
        elif operation == OperationType.MAX:
            return max(values) if values else 0
        elif operation == OperationType.MIN:
            return min(values) if values else 0

    def _store_result(self, workflow_id: str, result) -> None:
        self.shared_context['last_run'] = time.time()
        self.workflows[workflow_id] = {
            'last_result': result,
            'last_run': self.shared_context['last_run'],
        }

    def _evaluate_filter(self, value: float, condition: str) -> bool:
        try:
            if condition == 'even':
                return value % 2 == 0
            elif condition == 'odd':
                return value % 2 != 0
            elif condition == 'positive':
                return value > 0
            elif condition == 'negative':
                return value < 0
            elif condition.startswith('>'):
                return value > float(condition[1:])
            elif condition.startswith('<'):
                return value < float(condition[1:])
            return True
        except:
            return False


engine = WorkflowEngine()

INDEX_TEMPLATE = '''
        <html>
            <head>
                <title>Workflow Automation</title>
                <style>
                    textarea { width: 100%; height: 150px; }
                    .example { color: #666; font-size: 0.9em; }
                </style>
            </head>
            <body>
                <h1>Workflow Step Executor</h1>
                <form method="POST" action="/execute">
                    Workflow ID: <input type="text" name="workflow_id" required><br>
                    Step Configuration (JSON):<br>
                    <textarea name="step_config" required>
{
    "operation": "sum",
    "values": [1, 2, 3, 4, 5],
    "filter": "even"
}
                    </textarea>
                    <div class="example">
                        Example: {"operation": "average", "values": [10, 20, 30], "filter": ">15"}
                    </div>
                    <button type="submit">Execute Step</button>
                </form>
                <h2>Workflow Contexts:</h2>
                <pre>{contexts}</pre>
                {message}
            </body>
        </html>
        '''


class WorkflowApp:

    @cherrypy.expose
    def index(self):
        return INDEX_TEMPLATE.format(
            contexts=json.dumps(engine.workflows, indent=2),
            message=cherrypy.session.get('message', ''),
        )

    @cherrypy.expose
    def execute(self, workflow_id, step_config):
        result = engine.execute_step(workflow_id, step_config)
        if not str(result).startswith('Execution failed'):
            cherrypy.session['message'] = f"<div style='color:green'>Result: {result}</div>"
        else:
            cherrypy.session['message'] = f"<div style='color:red'>{result}</div>"
        raise cherrypy.HTTPRedirect('/')


if __name__ == '__main__':
    conf = {'/': {'tools.sessions.on': True, 'tools.staticdir.root': os.path.abspath(os.getcwd())}}
    cherrypy.quickstart(WorkflowApp(), '/', conf)
