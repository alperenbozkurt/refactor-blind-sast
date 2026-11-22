"""Dynamic JSON configuration evaluator web application.

Serves a small HTML form that accepts named JSON configurations, validates
them and keeps them in memory for inspection.
"""

import json
import math
from dataclasses import dataclass
from json import JSONDecodeError

from sanic import Sanic
from sanic.request import Request
from sanic.response import html

APP_NAME = 'ConfigEvaluator'

CONFIG_NAME_FIELD = 'config_name'
CONFIG_JSON_FIELD = 'config_json'

ALLOWED_CONFIG_TYPES = (dict, list)
INVALID_CONFIG_TYPE_MESSAGE = 'Configuration must be a JSON object or array'

SUCCESS_MESSAGE_TEMPLATE = (
    "<div style='color:green'>Config '{config_name}' applied successfully!</div>"
)
ERROR_MESSAGE_TEMPLATE = "<div style='color:red'>Error: {result}</div>"


@dataclass(frozen=True)
class ServerSettings:
    """Connection and runtime options for the embedded web server."""

    host: str = '0.0.0.0'
    port: int = 8000
    debug: bool = True


SERVER_SETTINGS = ServerSettings()

app = Sanic(APP_NAME)

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


class ConfigManager:
    """Validate and store named JSON configurations in memory."""

    def __init__(self):
        self.configs = {}

    def apply_config(self, config_name: str, config_json: str):
        """Parse *config_json* and store it under *config_name*.

        Returns True on success, otherwise a human readable error message.
        """
        try:
            config_value = json.loads(config_json)
            self._ensure_valid_config(config_value)
            self.configs[config_name] = config_value
            return True
        except JSONDecodeError as e:
            return f'Invalid JSON: {str(e)}'
        except Exception as e:
            return str(e)

    @staticmethod
    def _ensure_valid_config(config_value) -> None:
        """Reject top-level JSON values that are not objects or arrays."""
        if not isinstance(config_value, ALLOWED_CONFIG_TYPES):
            raise ValueError(INVALID_CONFIG_TYPE_MESSAGE)


config_manager = ConfigManager()


def _serialized_configs() -> str:
    """Return the currently stored configurations as formatted JSON."""
    return json.dumps(config_manager.configs, indent=2)


def _render_page(message: str = ''):
    """Build the HTML response for the form page."""
    return html(HTML_FORM.format(configs=_serialized_configs(), message=message))


def _build_success_message(config_name: str) -> str:
    """Render the success banner shown after a config is applied."""
    return SUCCESS_MESSAGE_TEMPLATE.format(config_name=config_name)


def _build_error_message(result: str) -> str:
    """Render the error banner shown when applying a config fails."""
    return ERROR_MESSAGE_TEMPLATE.format(result=result)


@app.get('/')
async def index(request: Request):
    return _render_page()


@app.post('/evaluate')
async def evaluate(request: Request):
    config_name = request.form.get(CONFIG_NAME_FIELD)
    config_json = request.form.get(CONFIG_JSON_FIELD)
    result = config_manager.apply_config(config_name, config_json)
    if result is True:
        message = _build_success_message(config_name)
    else:
        message = _build_error_message(result)
    return _render_page(message)


def main() -> None:
    """Run the web server with the configured settings."""
    app.run(
        host=SERVER_SETTINGS.host,
        port=SERVER_SETTINGS.port,
        debug=SERVER_SETTINGS.debug,
    )


if __name__ == '__main__':
    main()
