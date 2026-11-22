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


def _average(values):
    return sum(values) / len(values) if values else 0


def _max_or_zero(values):
    return max(values) if values else 0


def _min_or_zero(values):
    return min(values) if values else 0


_OPERATIONS = {
    OperationType.SUM: sum,
    OperationType.AVERAGE: _average,
    OperationType.MAX: _max_or_zero,
    OperationType.MIN: _min_or_zero,
}


class WorkflowEngine:

    def __init__(self):
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.shared_context = {'timestamp': time.time(), 'last_run': None}

    def execute_step(self, workflow_id: str, step_config: str):
        try:
            step = self._parse_step(step_config)
            self._validate_values(step.values)
            filtered_values = self._apply_filter(step)
            result = _OPERATIONS[step.operation](filtered_values)
            self._record_result(workflow_id, result)
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

    @staticmethod
    def _validate_values(values) -> None:
        if not all(isinstance(x, (int, float)) for x in values):
            raise ValueError('All values must be numbers')

    def _apply_filter(self, step: WorkflowStep) -> list:
        if not step.filter_condition:
            return step.values
        return [
            x for x in step.values
            if self._evaluate_filter(x, step.filter_condition)
        ]

    def _record_result(self, workflow_id: str, result) -> None:
        self.shared_context['last_run'] = time.time()
        self.workflows[workflow_id] = {
            'last_result': result,
            'last_run': self.shared_context['last_run'],
        }

    def _evaluate_filter(self, value: float, condition: str) -> bool:
        try:
            if condition == 'even':
                return value % 2 == 0
            if condition == 'odd':
                return value % 2 != 0
            if condition == 'positive':
                return value > 0
            if condition == 'negative':
                return value < 0
            if condition.startswith('>'):
                return value > float(condition[1:])
            if condition.startswith('<'):
                return value < float(condition[1:])
            return True
        except Exception:
            return False


engine = WorkflowEngine()

_INDEX_TEMPLATE = '\n        <html>\n            <head>\n                <title>Workflow Automation</title>\n                <style>\n                    textarea { width: 100%; height: 150px; }\n                    .example { color: #666; font-size: 0.9em; }\n                </style>\n            </head>\n            <body>\n                <h1>Workflow Step Executor</h1>\n                <form method="POST" action="/execute">\n                    Workflow ID: <input type="text" name="workflow_id" required><br>\n                    Step Configuration (JSON):<br>\n                    <textarea name="step_config" required>\n{\n    "operation": "sum",\n    "values": [1, 2, 3, 4, 5],\n    "filter": "even"\n}\n                    </textarea>\n                    <div class="example">\n                        Example: {"operation": "average", "values": [10, 20, 30], "filter": ">15"}\n                    </div>\n                    <button type="submit">Execute Step</button>\n                </form>\n                <h2>Workflow Contexts:</h2>\n                <pre>{contexts}</pre>\n                {message}\n            </body>\n        </html>\n        '

_FAILURE_PREFIX = 'Execution failed'


class WorkflowApp:

    @cherrypy.expose
    def index(self):
        return _INDEX_TEMPLATE.format(
            contexts=json.dumps(engine.workflows, indent=2),
            message=cherrypy.session.get('message', ''),
        )

    @cherrypy.expose
    def execute(self, workflow_id, step_config):
        result = engine.execute_step(workflow_id, step_config)
        if not str(result).startswith(_FAILURE_PREFIX):
            cherrypy.session['message'] = f"<div style='color:green'>Result: {result}</div>"
        else:
            cherrypy.session['message'] = f"<div style='color:red'>{result}</div>"
        raise cherrypy.HTTPRedirect('/')


if __name__ == '__main__':
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
        }
    }
    cherrypy.quickstart(WorkflowApp(), '/', conf)
