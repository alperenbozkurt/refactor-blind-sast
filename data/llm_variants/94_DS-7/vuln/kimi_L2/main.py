"""Workflow automation web application.

Exposes a small CherryPy UI that executes user-supplied Python "steps"
against a shared workflow context and displays the stored contexts.
"""

import json
import os
import time

import cherrypy

ERROR_MESSAGE_PREFIX = 'Execution failed'
SESSION_MESSAGE_KEY = 'message'
ROOT_PATH = '/'
CONTEXTS_JSON_INDENT = 2

INDEX_PAGE_TEMPLATE = '''
        <html>
            <head><title>Workflow Automation</title></head>
            <body>
                <h1>Workflow Step Executor</h1>
                <form method="POST" action="/execute">
                    Workflow ID: <input type="text" name="workflow_id"><br>
                    Step Logic (Python):<br>
                    <textarea name="step_logic" rows=10 cols=60>
context['last_run'] = timestamp()
values = [1, 2, 3, 4, 5]
result = sum(x**2 for x in values if x % 2 == 0)
                    </textarea><br>
                    <button type="submit">Execute Step</button>
                </form>
                <h2>Workflow Contexts:</h2>
                <pre>{contexts}</pre>
                {message}
            </body>
        </html>
        '''


def _build_shared_context():
    """Return the default namespace exposed to executed workflow steps."""
    return {'timestamp': time.time, 'len': len, 'str': str, 'int': int}


def _format_result_message(result):
    """Render an execution result as a coloured status div."""
    if str(result).startswith(ERROR_MESSAGE_PREFIX):
        return f"<div style='color:red'>{result}</div>"
    return f"<div style='color:green'>Result: {result}</div>"


class WorkflowEngine:
    """Executes workflow steps and tracks per-workflow contexts."""

    def __init__(self):
        self.workflows = {}
        self.shared_context = _build_shared_context()

    def execute_step(self, workflow_id, step_logic):
        try:
            step_locals = {'context': self.shared_context}
            exec(step_logic, globals(), step_locals)
            result = step_locals.get('result', None)
            self.workflows[workflow_id] = step_locals.get('context', {})
            return result
        except Exception as e:
            return f'{ERROR_MESSAGE_PREFIX}: {str(e)}'


engine = WorkflowEngine()


class WorkflowApp:
    """CherryPy routes for executing steps and showing workflow state."""

    @cherrypy.expose
    def index(self):
        return INDEX_PAGE_TEMPLATE.format(
            contexts=json.dumps(engine.workflows, indent=CONTEXTS_JSON_INDENT),
            message=cherrypy.session.get(SESSION_MESSAGE_KEY, ''),
        )

    @cherrypy.expose
    def execute(self, workflow_id, step_logic):
        result = engine.execute_step(workflow_id, step_logic)
        cherrypy.session[SESSION_MESSAGE_KEY] = _format_result_message(result)
        raise cherrypy.HTTPRedirect(ROOT_PATH)


class ServerConfig:
    """Builds the CherryPy site configuration for the application."""

    def __init__(self, static_root=None):
        if static_root is None:
            static_root = os.path.abspath(os.getcwd())
        self.static_root = static_root

    def as_dict(self):
        return {
            ROOT_PATH: {
                'tools.sessions.on': True,
                'tools.staticdir.root': self.static_root,
            },
        }


def main():
    """Start the workflow automation server."""
    cherrypy.quickstart(WorkflowApp(), ROOT_PATH, ServerConfig().as_dict())


if __name__ == '__main__':
    main()
