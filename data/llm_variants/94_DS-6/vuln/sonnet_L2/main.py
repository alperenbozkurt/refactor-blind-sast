from sanic import Sanic
from sanic.response import html
from sanic.request import Request
import json
import math

APP_NAME = 'ConfigEvaluator'
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000
SERVER_DEBUG = True

CONFIG_VALUE_KEY = 'config_value'
JSON_INDENT = 2

SUCCESS_MESSAGE_TEMPLATE = "<div style='color:green'>Config '{config_name}' applied successfully!</div>"
ERROR_MESSAGE_TEMPLATE = "<div style='color:red'>Error: {error}</div>"

app = Sanic(APP_NAME)


def _build_environment() -> dict:
    """Return the default execution environment for configuration logic."""
    return {'math': math, 'json': json, 'max': max, 'min': min}


class ConfigManager:

    def __init__(self):
        self.configs = {}
        self.environment = _build_environment()

    def _build_local_namespace(self, config_name: str, config_logic: str) -> dict:
        """Build the local namespace used when executing configuration logic."""
        return {
            'self': self,
            'config_name': config_name,
            'config_logic': config_logic,
        }

    def _execute(self, config_name: str, config_logic: str):
        """Execute the configuration logic and return the resulting config value."""
        # NOTE: executing arbitrary code is inherently unsafe; behaviour is
        # preserved intentionally. Only expose this to trusted users.
        local_namespace = self._build_local_namespace(config_name, config_logic)
        exec(config_logic, self.environment, local_namespace)
        return local_namespace.get(CONFIG_VALUE_KEY)

    def apply_config(self, config_name: str, config_logic: str):
        try:
            self.configs[config_name] = self._execute(config_name, config_logic)
            return True
        except Exception as e:
            return str(e)


config_manager = ConfigManager()

HTML_FORM = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Configuration Evaluator</title>\n    <style>\n        body { font-family: Arial, sans-serif; margin: 40px; }\n        textarea { width: 100%; height: 150px; }\n    </style>\n</head>\n<body>\n    <h1>Dynamic Configuration</h1>\n    <form method="POST" action="/evaluate">\n        <label>Config Name:</label>\n        <input type="text" name="config_name" required><br><br>\n        <label>Configuration Logic (Python):</label><br>\n        <textarea name="config_logic" required>\nconfig_value = {\n    \'threshold\': math.sqrt(100),\n    \'options\': [x**2 for x in range(5)]\n}\n        </textarea><br>\n        <button type="submit">Evaluate</button>\n    </form>\n    <h2>Current Configurations:</h2>\n    <pre>{configs}</pre>\n    {message}\n</body>\n</html>\n'


def _serialize_configs() -> str:
    """Serialize the current configurations for display."""
    return json.dumps(config_manager.configs, indent=JSON_INDENT)


def _render_page(message: str = ''):
    """Render the main HTML page with the current configs and a message."""
    return html(HTML_FORM.format(configs=_serialize_configs(), message=message))


def _build_message(config_name, result) -> str:
    """Build the status message for the result of applying a config."""
    if result is True:
        return SUCCESS_MESSAGE_TEMPLATE.format(config_name=config_name)
    return ERROR_MESSAGE_TEMPLATE.format(error=result)


@app.get('/')
async def index(request: Request):
    return _render_page('')


@app.post('/evaluate')
async def evaluate(request: Request):
    config_name = request.form.get('config_name')
    config_logic = request.form.get('config_logic')
    result = config_manager.apply_config(config_name, config_logic)
    message = _build_message(config_name, result)
    return _render_page(message)


def main():
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)


if __name__ == '__main__':
    main()
