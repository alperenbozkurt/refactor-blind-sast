from sanic import Sanic
from sanic.response import html
from sanic.request import Request
import json
import math
from json import JSONDecodeError

app = Sanic('ConfigEvaluator')


class ConfigManager:

    def __init__(self):
        self.configs = {}

    def apply_config(self, config_name: str, config_json: str):
        try:
            config_value = json.loads(config_json)
            if not isinstance(config_value, (dict, list)):
                raise ValueError('Configuration must be a JSON object or array')
            self.configs[config_name] = config_value
            return True
        except JSONDecodeError as e:
            return f'Invalid JSON: {e}'
        except Exception as e:
            return str(e)


config_manager = ConfigManager()

HTML_FORM = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Configuration Evaluator</title>\n    <style>\n        body { font-family: Arial, sans-serif; margin: 40px; }\n        textarea { width: 100%; height: 150px; }\n        .example { color: #666; font-size: 0.9em; margin-top: 5px; }\n    </style>\n</head>\n<body>\n    <h1>Dynamic Configuration</h1>\n    <form method="POST" action="/evaluate">\n        <label>Config Name:</label>\n        <input type="text" name="config_name" required><br><br>\n        <label>Configuration (JSON):</label><br>\n        <textarea name="config_json" required>\n{\n    "threshold": 10,\n    "options": [0, 1, 4, 9, 16]\n}\n        </textarea>\n        <div class="example">Example: {"setting": "value", "numbers": [1, 2, 3]}</div>\n        <br>\n        <button type="submit">Evaluate</button>\n    </form>\n    <h2>Current Configurations:</h2>\n    <pre>{configs}</pre>\n    {message}\n</body>\n</html>\n'


def _render_page(message: str = ''):
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
    config_json = request.form.get('config_json')
    result = config_manager.apply_config(config_name, config_json)
    if result is True:
        message = f"<div style='color:green'>Config '{config_name}' applied successfully!</div>"
    else:
        message = f"<div style='color:red'>Error: {result}</div>"
    return _render_page(message)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
