"""Dynamic configuration evaluator web application.

A small Sanic app that evaluates user-supplied Python snippets which define a
``config_value`` and stores the resulting configurations in a shared
:class:`ConfigManager`.
"""

import json
import math
from dataclasses import dataclass
from typing import Any, Dict

from sanic import Sanic
from sanic.request import Request
from sanic.response import html

APP_NAME = 'ConfigEvaluator'

INDEX_ROUTE = '/'
EVALUATE_ROUTE = '/evaluate'

CONFIG_VALUE_KEY = 'config_value'

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


@dataclass(frozen=True)
class ServerConfig:
    """Runtime settings for the development server."""

    host: str = '0.0.0.0'
    port: int = 8000
    debug: bool = True


SERVER_CONFIG = ServerConfig()

app = Sanic(APP_NAME)


def _default_environment() -> Dict[str, Any]:
    """Build the global namespace available to evaluated configuration logic."""
    return {'math': math, 'json': json, 'max': max, 'min': min}


class ConfigManager:

    def __init__(self):
        self.configs = {}
        self.environment = _default_environment()

    def apply_config(self, config_name: str, config_logic: str):
        try:
            namespace = locals()
            exec(config_logic, self.environment, namespace)
            self.configs[config_name] = namespace.get(CONFIG_VALUE_KEY)
            return True
        except Exception as error:
            return str(error)


config_manager = ConfigManager()


def _render_configs() -> str:
    """Serialize the currently stored configurations for display."""
    return json.dumps(config_manager.configs, indent=2)


def _render_page(message: str = '') -> str:
    """Render the HTML form together with the current configs and a message."""
    return HTML_FORM.format(configs=_render_configs(), message=message)


def _success_message(config_name: str) -> str:
    return f"<div style='color:green'>Config '{config_name}' applied successfully!</div>"


def _error_message(error: str) -> str:
    return f"<div style='color:red'>Error: {error}</div>"


@app.get(INDEX_ROUTE)
async def index(request: Request):
    return html(_render_page())


@app.post(EVALUATE_ROUTE)
async def evaluate(request: Request):
    config_name = request.form.get('config_name')
    config_logic = request.form.get('config_logic')
    result = config_manager.apply_config(config_name, config_logic)
    if result is True:
        message = _success_message(config_name)
    else:
        message = _error_message(result)
    return html(_render_page(message))


def main() -> None:
    """Start the development server with the configured settings."""
    app.run(host=SERVER_CONFIG.host, port=SERVER_CONFIG.port, debug=SERVER_CONFIG.debug)


if __name__ == '__main__':
    main()
