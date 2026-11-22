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


_OPERATIONS = {
    OperationType.SUM: sum,
    OperationType.AVERAGE: lambda vals: sum(vals) / len(vals) if vals else 0,
    OperationType.MAX: lambda vals: max(vals) if vals else 0,
    OperationType.MIN: lambda vals: min(vals) if vals else 0,
}

_SIMPLE_FILTERS = {
    'even': lambda v: v % 2 == 0,
    'odd': lambda v: v % 2 != 0,
    'positive': lambda v: v > 0,
    'negative': lambda v: v < 0,
}


class WorkflowEngine:

    def __init__(self):
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.shared_context = {'timestamp': time.time(), 'last_run': None}

    def execute_step(self, workflow_id: str, step_config: str):
        try:
            step = self._parse_step(step_config)
            if not all(isinstance(x, (int, float)) for x in step.values):
                raise ValueError('All values must be numbers')

            values = step.values
            if step.filter_condition:
                condition = step.filter_condition
                values = [x for x in values if self._evaluate_filter(x, condition)]

            result = _OPERATIONS[step.operation](values)

            last_run = time.time()
            self.shared_context['last_run'] = last_run
            self.workflows[workflow_id] = {'last_result': result, 'last_run': last_run}
            return result
        except json.JSONDecodeError as e:
            return f'Invalid configuration: {str(e)}'
        except ValueError as e:
            return f'Validation error: {str(e)}'
        except Exception as e:
            return f'Execution failed: {str(e)}'

    @staticmethod
    def _parse_step(step_config: str) -> WorkflowStep:
        step_data = json.loads(step_config)
        return WorkflowStep(
            operation=OperationType(step_data.get('operation')),
            values=step_data.get('values', []),
            filter_condition=step_data.get('filter'),
        )

    def _evaluate_filter(self, value: float, condition: str) -> bool:
        try:
            if condition in _SIMPLE_FILTERS:
                return _SIMPLE_FILTERS[condition](value)
            if condition.startswith('>'):
                return value > float(condition[1:])
            if condition.startswith('<'):
                return value < float(condition[1:])
            return True
        except Exception:
            return False


engine = WorkflowEngine()


class WorkflowApp:

    @cherrypy.expose
    def index(self):
        return '\n        <html>\n            <head>\n                <title>Workflow Automation</title>\n                <style>\n                    textarea { width: 100%; height: 150px; }\n                    .example { color: #666; font-size: 0.9em; }\n                </style>\n            </head>\n            <body>\n                <h1>Workflow Step Executor</h1>\n                <form method="POST" action="/execute">\n                    Workflow ID: <input type="text" name="workflow_id" required><br>\n                    Step Configuration (JSON):<br>\n                    <textarea name="step_config" required>\n{\n    "operation": "sum",\n    "values": [1, 2, 3, 4, 5],\n    "filter": "even"\n}\n                    </textarea>\n                    <div class="example">\n                        Example: {"operation": "average", "values": [10, 20, 30], "filter": ">15"}\n                    </div>\n                    <button type="submit">Execute Step</button>\n                </form>\n                <h2>Workflow Contexts:</h2>\n                <pre>{contexts}</pre>\n                {message}\n            </body>\n        </html>\n        '.format(contexts=json.dumps(engine.workflows, indent=2), message=cherrypy.session.get('message', ''))

    @cherrypy.expose
    def execute(self, workflow_id, step_config):
        result = engine.execute_step(workflow_id, step_config)
        if str(result).startswith('Execution failed'):
            message = f"<div style='color:red'>{result}</div>"
        else:
            message = f"<div style='color:green'>Result: {result}</div>"
        cherrypy.session['message'] = message
        raise cherrypy.HTTPRedirect('/')


if __name__ == '__main__':
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
        }
    }
    cherrypy.quickstart(WorkflowApp(), '/', conf)
