import json
import math

from sanic import Sanic
from sanic.request import Request
from sanic.response import html

app = Sanic('ConfigEvaluator')

HTML_FORM = (
    '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Configuration Evaluator</title>\n'
    '    <style>\n        body { font-family: Arial, sans-serif; margin: 40px; }\n'
    '        textarea { width: 100%; height: 150px; }\n    </style>\n</head>\n<body>\n'
    '    <h1>Dynamic Configuration</h1>\n'
    '    <form method="POST" action="/evaluate">\n'
    '        <label>Config Name:</label>\n'
    '        <input type="text" name="config_name" required><br><br>\n'
    '        <label>Configuration Logic (Python):</label><br>\n'
    '        <textarea name="config_logic" required>\n'
    "config_value = {\n    'threshold': math.sqrt(100),\n"
    "    'options': [x**2 for x in range(5)]\n}\n"
    '        </textarea><br>\n'
    '        <button type="submit">Evaluate</button>\n    </form>\n'
    '    <h2>Current Configurations:</h2>\n    <pre>{configs}</pre>\n'
    '    {message}\n</body>\n</html>\n'
)

CONFIG_VALUE_KEY = 'config_value'


class ConfigManager:
    """Stores named configurations produced by evaluating config logic."""

    def __init__(self):
        self.configs = {}
        self.environment = {'math': math, 'json': json, 'max': max, 'min': min}

    def apply_config(self, config_name: str, config_logic: str):
        """Run the config logic and store its `config_value`.

        Returns True on success, or the error message as a string on failure.
        """
        # The namespace mirrors the local variables that were visible to the
        # executed code in the original implementation.
        local_namespace = {
            'self': self,
            'config_name': config_name,
            'config_logic': config_logic,
        }
        try:
            exec(config_logic, self.environment, local_namespace)
            self.configs[config_name] = local_namespace.get(CONFIG_VALUE_KEY)
            return True
        except Exception as e:
            return str(e)


config_manager = ConfigManager()


def render_page(message: str = ''):
    """Render the HTML form with the current configurations and a message."""
    configs_json = json.dumps(config_manager.configs, indent=2)
    return html(HTML_FORM.format(configs=configs_json, message=message))


def build_message(config_name, result):
    """Build the status message shown after an evaluation attempt."""
    if result is True:
        return f"<div style='color:green'>Config '{config_name}' applied successfully!</div>"
    return f"<div style='color:red'>Error: {result}</div>"


@app.get('/')
async def index(request: Request):
    return render_page()


@app.post('/evaluate')
async def evaluate(request: Request):
    config_name = request.form.get('config_name')
    config_logic = request.form.get('config_logic')
    result = config_manager.apply_config(config_name, config_logic)
    return render_page(build_message(config_name, result))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
