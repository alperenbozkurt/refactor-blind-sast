import cherrypy
import json
import time
import os
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

EMPTY_RESULT_DEFAULT = 0

FILTER_EVEN = 'even'
FILTER_ODD = 'odd'
FILTER_POSITIVE = 'positive'
FILTER_NEGATIVE = 'negative'
FILTER_GREATER_PREFIX = '>'
FILTER_LESS_PREFIX = '<'

ERROR_PREFIX_INVALID_CONFIG = 'Invalid configuration'
ERROR_PREFIX_VALIDATION = 'Validation error'
ERROR_PREFIX_EXECUTION = 'Execution failed'

SUCCESS_MESSAGE_TEMPLATE = "<div style='color:green'>Result: {result}</div>"
FAILURE_MESSAGE_TEMPLATE = "<div style='color:red'>{result}</div>"

SESSION_MESSAGE_KEY = 'message'
INDEX_REDIRECT_URL = '/'
MOUNT_POINT = '/'

# NOTE: This template is rendered with str.format, exactly as in the original
# module, so its behaviour is unchanged.
INDEX_TEMPLATE = '\n        <html>\n            <head>\n                <title>Workflow Automation</title>\n                <style>\n                    textarea { width: 100%; height: 150px; }\n                    .example { color: #666; font-size: 0.9em; }\n                </style>\n            </head>\n            <body>\n                <h1>Workflow Step Executor</h1>\n                <form method="POST" action="/execute">\n                    Workflow ID: <input type="text" name="workflow_id" required><br>\n                    Step Configuration (JSON):<br>\n                    <textarea name="step_config" required>\n{\n    "operation": "sum",\n    "values": [1, 2, 3, 4, 5],\n    "filter": "even"\n}\n                    </textarea>\n                    <div class="example">\n                        Example: {"operation": "average", "values": [10, 20, 30], "filter": ">15"}\n                    </div>\n                    <button type="submit">Execute Step</button>\n                </form>\n                <h2>Workflow Contexts:</h2>\n                <pre>{contexts}</pre>\n                {message}\n            </body>\n        </html>\n        '


# --------------------------------------------------------------------------- #
# Domain types
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Pure helpers: operations
# --------------------------------------------------------------------------- #

def _sum_values(values):
    return sum(values)


def _average_values(values):
    return sum(values) / len(values) if values else EMPTY_RESULT_DEFAULT


def _max_value(values):
    return max(values) if values else EMPTY_RESULT_DEFAULT


def _min_value(values):
    return min(values) if values else EMPTY_RESULT_DEFAULT


OPERATION_HANDLERS = {
    OperationType.SUM: _sum_values,
    OperationType.AVERAGE: _average_values,
    OperationType.MAX: _max_value,
    OperationType.MIN: _min_value,
}


def _apply_operation(operation: OperationType, values):
    return OPERATION_HANDLERS[operation](values)


# --------------------------------------------------------------------------- #
# Pure helpers: parsing / validation
# --------------------------------------------------------------------------- #

def _parse_step(step_config: str) -> WorkflowStep:
    step_data = json.loads(step_config)
    return WorkflowStep(
        operation=OperationType(step_data.get('operation')),
        values=step_data.get('values', []),
        filter_condition=step_data.get('filter'),
    )


def _validate_values(values) -> None:
    if not all((isinstance(x, (int, float)) for x in values)):
        raise ValueError('All values must be numbers')


# --------------------------------------------------------------------------- #
# Pure helpers: filters
# --------------------------------------------------------------------------- #

NAMED_FILTERS = {
    FILTER_EVEN: lambda value: value % 2 == 0,
    FILTER_ODD: lambda value: value % 2 != 0,
    FILTER_POSITIVE: lambda value: value > 0,
    FILTER_NEGATIVE: lambda value: value < 0,
}


def _matches_condition(value, condition) -> bool:
    if condition in NAMED_FILTERS:
        return NAMED_FILTERS[condition](value)
    if condition.startswith(FILTER_GREATER_PREFIX):
        return value > float(condition[1:])
    if condition.startswith(FILTER_LESS_PREFIX):
        return value < float(condition[1:])
    return True


# --------------------------------------------------------------------------- #
# Error formatting
# --------------------------------------------------------------------------- #

def _format_error(prefix: str, error: Exception) -> str:
    return f'{prefix}: {str(error)}'


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #

class WorkflowEngine:

    def __init__(self):
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.shared_context = {'timestamp': time.time(), 'last_run': None}

    def execute_step(self, workflow_id: str, step_config: str):
        try:
            step = _parse_step(step_config)
            _validate_values(step.values)
            filtered_values = self._apply_filter(step)
            result = _apply_operation(step.operation, filtered_values)
            self._record_result(workflow_id, result)
            return result
        except json.JSONDecodeError as e:
            return _format_error(ERROR_PREFIX_INVALID_CONFIG, e)
        except ValueError as e:
            return _format_error(ERROR_PREFIX_VALIDATION, e)
        except Exception as e:
            return _format_error(ERROR_PREFIX_EXECUTION, e)

    def _apply_filter(self, step: WorkflowStep):
        if step.filter_condition:
            return [
                x for x in step.values
                if self._evaluate_filter(x, step.filter_condition)
            ]
        return step.values

    def _record_result(self, workflow_id: str, result) -> None:
        self.shared_context['last_run'] = time.time()
        self.workflows[workflow_id] = {
            'last_result': result,
            'last_run': self.shared_context['last_run'],
        }

    def _evaluate_filter(self, value: float, condition: str) -> bool:
        try:
            return _matches_condition(value, condition)
        except Exception:
            return False


engine = WorkflowEngine()


# --------------------------------------------------------------------------- #
# Web application
# --------------------------------------------------------------------------- #

def _build_result_message(result) -> str:
    if not str(result).startswith(ERROR_PREFIX_EXECUTION):
        return SUCCESS_MESSAGE_TEMPLATE.format(result=result)
    return FAILURE_MESSAGE_TEMPLATE.format(result=result)


def _build_server_config() -> dict:
    return {
        MOUNT_POINT: {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
        }
    }


class WorkflowApp:

    @cherrypy.expose
    def index(self):
        return INDEX_TEMPLATE.format(
            contexts=json.dumps(engine.workflows, indent=2),
            message=cherrypy.session.get(SESSION_MESSAGE_KEY, ''),
        )

    @cherrypy.expose
    def execute(self, workflow_id, step_config):
        result = engine.execute_step(workflow_id, step_config)
        cherrypy.session[SESSION_MESSAGE_KEY] = _build_result_message(result)
        raise cherrypy.HTTPRedirect(INDEX_REDIRECT_URL)


if __name__ == '__main__':
    conf = _build_server_config()
    cherrypy.quickstart(WorkflowApp(), MOUNT_POINT, conf)
