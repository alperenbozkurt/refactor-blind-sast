"""Sanic application for evaluating and storing JSON configurations."""

import json
import math
from json import JSONDecodeError

from sanic import Sanic
from sanic.request import Request
from sanic.response import html

app = Sanic('ConfigEvaluator')


class ConfigManager:
    """In-memory store for named JSON configurations."""

    def __init__(self):
        self.configs = {}

    def apply_config(self, config_name: str, config_json: str):
        """Parse ``config_json`` and store it under ``config_name``.

        Returns ``True`` on success, otherwise an error message string.
        """
        try:
            config_value = json.loads(config_json)
            if not isinstance(config_value, (dict, list)):
                raise ValueError(
                    'Configuration must be a JSON object or array'
                )
            self.configs[config_name] = config_value
            return True
        except JSONDecodeError as e:
            return f'Invalid JSON: {e}'
        except Exception as e:
            return str(e)


config_manager = ConfigManager()

HTML_FORM = """
<!DOCTYPE html>
<html>
<head>
    <title>Configuration Evaluator</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        textarea { width: 100%; height: 150px; }
        .example { color: #666; font-size: 0.9em; margin-top: 5px; }
    </style>
</head>
<body>
    <h1>Dynamic Configuration</h1>
    <form method="POST" action="/evaluate">
        <label>Config Name:</label>
        <input type="text" name="config_name" required><br><br>
        <label>Configuration (JSON):</label><br>
        <textarea name="config_json" required>
{
    "threshold": 10,
    "options": [0, 1, 4, 9, 16]
}
        </textarea>
        <div class="example">Example: {"setting": "value", "numbers": [1, 2, 3]}</div>
        <br>
        <button type="submit">Evaluate</button>
    </form>
    <h2>Current Configurations:</h2>
    <pre>{configs}</pre>
    {message}
</body>
</html>
"""


def _render_page(message=''):
    """Render the HTML form with the current configs and a status message."""
    return HTML_FORM.format(
        configs=json.dumps(config_manager.configs, indent=2),
        message=message,
    )


@app.get('/')
async def index(request: Request):
    return html(_render_page())


@app.post('/evaluate')
async def evaluate(request: Request):
    config_name = request.form.get('config_name')
    config_json = request.form.get('config_json')

    result = config_manager.apply_config(config_name, config_json)
    if result is True:
        message = (
            f"<div style='color:green'>Config '{config_name}' "
            'applied successfully!</div>'
        )
    else:
        message = f"<div style='color:red'>Error: {result}</div>"

    return html(_render_page(message))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
