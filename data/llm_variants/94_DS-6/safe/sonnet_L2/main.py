import json
import math
from json import JSONDecodeError

from sanic import Sanic
from sanic.request import Request
from sanic.response import html

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
APP_NAME = 'ConfigEvaluator'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000
SERVER_DEBUG = True

ROUTE_INDEX = '/'
ROUTE_EVALUATE = '/evaluate'

FORM_FIELD_CONFIG_NAME = 'config_name'
FORM_FIELD_CONFIG_JSON = 'config_json'

ALLOWED_CONFIG_TYPES = (dict, list)
JSON_INDENT = 2

ERROR_INVALID_TYPE = 'Configuration must be a JSON object or array'
ERROR_INVALID_JSON_PREFIX = 'Invalid JSON: '

SUCCESS_MESSAGE_TEMPLATE = "<div style='color:green'>Config '{name}' applied successfully!</div>"
ERROR_MESSAGE_TEMPLATE = "<div style='color:red'>Error: {error}</div>"

HTML_FORM = '''
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
'''

app = Sanic(APP_NAME)


# --------------------------------------------------------------------------- #
# Configuration management
# --------------------------------------------------------------------------- #
def _parse_config(config_json: str):
    """Parse a JSON string and validate that it is an object or array."""
    config_value = json.loads(config_json)
    if not isinstance(config_value, ALLOWED_CONFIG_TYPES):
        raise ValueError(ERROR_INVALID_TYPE)
    return config_value


class ConfigManager:

    def __init__(self):
        self.configs = {}

    def apply_config(self, config_name: str, config_json: str):
        try:
            self.configs[config_name] = _parse_config(config_json)
            return True
        except JSONDecodeError as e:
            return f'{ERROR_INVALID_JSON_PREFIX}{str(e)}'
        except Exception as e:
            return str(e)


config_manager = ConfigManager()


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #
def _serialize_configs(configs) -> str:
    return json.dumps(configs, indent=JSON_INDENT)


def _build_message(config_name, result) -> str:
    if result is True:
        return SUCCESS_MESSAGE_TEMPLATE.format(name=config_name)
    return ERROR_MESSAGE_TEMPLATE.format(error=result)


def _render_page(message: str = ''):
    return html(HTML_FORM.format(
        configs=_serialize_configs(config_manager.configs),
        message=message,
    ))


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.get(ROUTE_INDEX)
async def index(request: Request):
    return _render_page()


@app.post(ROUTE_EVALUATE)
async def evaluate(request: Request):
    config_name = request.form.get(FORM_FIELD_CONFIG_NAME)
    config_json = request.form.get(FORM_FIELD_CONFIG_JSON)
    result = config_manager.apply_config(config_name, config_json)
    message = _build_message(config_name, result)
    return _render_page(message)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
