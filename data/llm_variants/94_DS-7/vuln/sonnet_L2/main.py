import cherrypy
import json
import time
import os

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

FAILURE_PREFIX = 'Execution failed'
SESSION_MESSAGE_KEY = 'message'
REDIRECT_TARGET = '/'
MOUNT_POINT = '/'

SUCCESS_MESSAGE_TEMPLATE = "<div style='color:green'>Result: {result}</div>"
ERROR_MESSAGE_TEMPLATE = "<div style='color:red'>{result}</div>"

INDEX_TEMPLATE = """
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
        """


# --------------------------------------------------------------------------- #
# Workflow engine
# --------------------------------------------------------------------------- #

def _build_shared_context():
    """Create the initial context exposed to workflow steps."""
    return {'timestamp': time.time, 'len': len, 'str': str, 'int': int}


def _format_failure(error):
    """Build the standard failure message for an exception."""
    return f'{FAILURE_PREFIX}: {str(error)}'


class WorkflowEngine:
    """Executes workflow step logic and stores resulting contexts.

    NOTE: step logic is executed with ``exec`` and therefore must only come
    from fully trusted sources.
    """

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
            return _format_failure(e)


engine = WorkflowEngine()


# --------------------------------------------------------------------------- #
# Web application helpers
# --------------------------------------------------------------------------- #

def _is_failure(result):
    """Return True if the step result represents a failed execution."""
    return str(result).startswith(FAILURE_PREFIX)


def _build_result_message(result):
    """Render the HTML flash message for a step result."""
    template = ERROR_MESSAGE_TEMPLATE if _is_failure(result) else SUCCESS_MESSAGE_TEMPLATE
    return template.format(result=result) if not _is_failure(result) else f"<div style='color:red'>{result}</div>"


def _render_index(contexts, message):
    """Render the index page."""
    return INDEX_TEMPLATE.format(contexts=json.dumps(contexts, indent=2), message=message)


def build_config():
    """Return the CherryPy configuration for the application."""
    return {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
        }
    }


# --------------------------------------------------------------------------- #
# Web application
# --------------------------------------------------------------------------- #

class WorkflowApp:

    @cherrypy.expose
    def index(self):
        message = cherrypy.session.get(SESSION_MESSAGE_KEY, '')
        return _render_index(engine.workflows, message)

    @cherrypy.expose
    def execute(self, workflow_id, step_logic):
        result = engine.execute_step(workflow_id, step_logic)
        cherrypy.session[SESSION_MESSAGE_KEY] = _build_result_message(result)
        raise cherrypy.HTTPRedirect(REDIRECT_TARGET)


if __name__ == '__main__':
    conf = build_config()
    cherrypy.quickstart(WorkflowApp(), MOUNT_POINT, conf)
