"""Sanic web app for evaluating and storing dynamic configuration snippets."""

import json
import math

from sanic import Sanic
from sanic.request import Request
from sanic.response import html

app = Sanic('ConfigEvaluator')


class ConfigManager:
    """Evaluate user-supplied Python snippets and store the resulting configs."""

    def __init__(self):
        self.configs = {}
        self.environment = {
            'math': math,
            'json': json,
            'max': max,
            'min': min,
        }

    def apply_config(self, config_name: str, config_logic: str):
        """Evaluate ``config_logic`` and store ``config_value`` under ``config_name``.

        Returns True on success, otherwise the evaluation error as a string.
        """
        try:
            exec(config_logic, self.environment, locals())
            self.configs[config_name] = locals().get('config_value')
            return True
        except Exception as exc:
            return str(exc)


config_manager = ConfigManager()

HTML_FORM = """
<!DOCTYPE html>
<html>
<head>
    <title>Configuration Evaluator</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        textarea { width: 100%; height: 150px; }
    </style>
</head>
<body>
    <h1>Dynamic Configuration</h1>
    <form method="POST" action="/evaluate">
        <label>Config Name:</label>
        <input type="text" name="config_name" required><br><br>
        <label>Configuration Logic (Python):</label><br>
        <textarea name="config_logic" required>
config_value = {
    'threshold': math.sqrt(100),
    'options': [x**2 for x in range(5)]
}
        </textarea><br>
        <button type="submit">Evaluate</button>
    </form>
    <h2>Current Configurations:</h2>
    <pre>{configs}</pre>
    {message}
</body>
</html>
"""


def _render_page(message: str = ''):
    """Render the form page with the current configs and a status message."""
    return html(
        HTML_FORM.format(
            configs=json.dumps(config_manager.configs, indent=2),
            message=message,
        )
    )


@app.get('/')
async def index(request: Request):
    return _render_page()


@app.post('/evaluate')
async def evaluate(request: Request):
    config_name = request.form.get('config_name')
    config_logic = request.form.get('config_logic')
    result = config_manager.apply_config(config_name, config_logic)
    if result is True:
        message = (
            f"<div style='color:green'>Config '{config_name}' "
            'applied successfully!</div>'
        )
    else:
        message = f"<div style='color:red'>Error: {result}</div>"
    return _render_page(message)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
