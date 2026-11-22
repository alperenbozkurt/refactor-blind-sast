"""Workflow automation web application.

A small CherryPy service that executes single workflow steps (sum, average,
max, min) over a list of numeric values, with optional value filtering, and
renders the stored per-workflow results on a simple HTML page.
"""

import cherrypy
import json
import time
import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Keys of the JSON step configuration payload.
CONFIG_KEY_OPERATION = 'operation'
CONFIG_KEY_VALUES = 'values'
CONFIG_KEY_FILTER = 'filter'

# Keys of the shared context and per-workflow records.
CONTEXT_KEY_TIMESTAMP = 'timestamp'
CONTEXT_KEY_LAST_RUN = 'last_run'
WORKFLOW_KEY_LAST_RESULT = 'last_result'

# Error message prefixes (errors are returned as strings, not raised).
ERROR_INVALID_CONFIGURATION = 'Invalid configuration'
ERROR_VALIDATION = 'Validation error'
ERROR_EXECUTION_FAILED = 'Execution failed'
ERROR_NON_NUMERIC_VALUES = 'All values must be numbers'

# Named filter conditions.
FILTER_EVEN = 'even'
FILTER_ODD = 'odd'
FILTER_POSITIVE = 'positive'
FILTER_NEGATIVE = 'negative'

# Prefixes for threshold filter conditions (e.g. ">15").
FILTER_GREATER_THAN_PREFIX = '>'
FILTER_LESS_THAN_PREFIX = '<'

# HTTP layer.
SESSION_MESSAGE_KEY = 'message'
HOME_ROUTE = '/'


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


# ---------------------------------------------------------------------------
# Operation handlers
# ---------------------------------------------------------------------------

def _sum_values(values: list) -> Any:
    return sum(values)


def _average_values(values: list) -> Any:
    return sum(values) / len(values) if values else 0


def _max_value(values: list) -> Any:
    return max(values) if values else 0


def _min_value(values: list) -> Any:
    return min(values) if values else 0


_OPERATION_HANDLERS: Dict[OperationType, Callable[[list], Any]] = {
    OperationType.SUM: _sum_values,
    OperationType.AVERAGE: _average_values,
    OperationType.MAX: _max_value,
    OperationType.MIN: _min_value,
}


# ---------------------------------------------------------------------------
# Filter predicates
# ---------------------------------------------------------------------------

def _is_even(value: float) -> bool:
    return value % 2 == 0


def _is_odd(value: float) -> bool:
    return value % 2 != 0


def _is_positive(value: float) -> bool:
    return value > 0


def _is_negative(value: float) -> bool:
    return value < 0


_NAMED_FILTERS: Dict[str, Callable[[float], bool]] = {
    FILTER_EVEN: _is_even,
    FILTER_ODD: _is_odd,
    FILTER_POSITIVE: _is_positive,
    FILTER_NEGATIVE: _is_negative,
}


# ---------------------------------------------------------------------------
# Workflow engine
# ---------------------------------------------------------------------------

class WorkflowEngine:
    """Executes workflow steps and tracks the last result of each workflow."""

    def __init__(self):
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.shared_context = {
            CONTEXT_KEY_TIMESTAMP: time.time(),
            CONTEXT_KEY_LAST_RUN: None,
        }

    def execute_step(self, workflow_id: str, step_config: str):
        try:
            step = self._parse_step_config(step_config)
            filtered_values = self._apply_filter(step)
            result = _OPERATION_HANDLERS[step.operation](filtered_values)
            self._record_result(workflow_id, result)
            return result
        except json.JSONDecodeError as e:
            return f'{ERROR_INVALID_CONFIGURATION}: {e}'
        except ValueError as e:
            return f'{ERROR_VALIDATION}: {e}'
        except Exception as e:
            return f'{ERROR_EXECUTION_FAILED}: {e}'

    def _parse_step_config(self, step_config: str) -> WorkflowStep:
        step_data = json.loads(step_config)
        step = WorkflowStep(
            operation=OperationType(step_data.get(CONFIG_KEY_OPERATION)),
            values=step_data.get(CONFIG_KEY_VALUES, []),
            filter_condition=step_data.get(CONFIG_KEY_FILTER),
        )
        self._validate_values(step.values)
        return step

    @staticmethod
    def _validate_values(values: list) -> None:
        if not all(isinstance(x, (int, float)) for x in values):
            raise ValueError(ERROR_NON_NUMERIC_VALUES)

    def _apply_filter(self, step: WorkflowStep) -> list:
        if step.filter_condition:
            return [
                value
                for value in step.values
                if self._evaluate_filter(value, step.filter_condition)
            ]
        return step.values

    def _record_result(self, workflow_id: str, result: Any) -> None:
        self.shared_context[CONTEXT_KEY_LAST_RUN] = time.time()
        self.workflows[workflow_id] = {
            WORKFLOW_KEY_LAST_RESULT: result,
            CONTEXT_KEY_LAST_RUN: self.shared_context[CONTEXT_KEY_LAST_RUN],
        }

    def _evaluate_filter(self, value: float, condition: str) -> bool:
        try:
            if condition in _NAMED_FILTERS:
                return _NAMED_FILTERS[condition](value)
            if condition.startswith(FILTER_GREATER_THAN_PREFIX):
                return value > float(condition[1:])
            if condition.startswith(FILTER_LESS_THAN_PREFIX):
                return value < float(condition[1:])
            return True
        except:
            # Any evaluation problem means the value does not match.
            return False


engine = WorkflowEngine()


# ---------------------------------------------------------------------------
# Web application
# ---------------------------------------------------------------------------

INDEX_PAGE_TEMPLATE = """
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
        """


def _format_result_message(result: Any) -> str:
    """Wrap an execution result in the HTML banner shown on the index page."""
    if str(result).startswith(ERROR_EXECUTION_FAILED):
        return f"<div style='color:red'>{result}</div>"
    return f"<div style='color:green'>Result: {result}</div>"


class WorkflowApp:
    """CherryPy request handlers for the workflow step executor."""

    @cherrypy.expose
    def index(self):
        return INDEX_PAGE_TEMPLATE.format(
            contexts=json.dumps(engine.workflows, indent=2),
            message=cherrypy.session.get(SESSION_MESSAGE_KEY, ''),
        )

    @cherrypy.expose
    def execute(self, workflow_id, step_config):
        result = engine.execute_step(workflow_id, step_config)
        cherrypy.session[SESSION_MESSAGE_KEY] = _format_result_message(result)
        raise cherrypy.HTTPRedirect(HOME_ROUTE)


# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServerConfig:
    """Settings used when starting the CherryPy server."""

    mount_point: str = HOME_ROUTE
    sessions_enabled: bool = True
    static_root: str = field(default_factory=lambda: os.path.abspath(os.getcwd()))

    def as_cherrypy_config(self) -> Dict[str, Any]:
        return {
            self.mount_point: {
                'tools.sessions.on': self.sessions_enabled,
                'tools.staticdir.root': self.static_root,
            }
        }


def main() -> None:
    config = ServerConfig()
    cherrypy.quickstart(WorkflowApp(), config.mount_point, config.as_cherrypy_config())


if __name__ == '__main__':
    main()
