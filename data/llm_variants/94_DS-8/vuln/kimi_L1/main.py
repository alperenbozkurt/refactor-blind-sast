"""Quart web application that generates JSON API responses from templates.

User-supplied Python snippets are executed to define template variables,
which are then interpolated into the selected response template.
"""

import asyncio
import inspect
import json
from typing import Any, Dict

from quart import Quart, jsonify, request

app = Quart(__name__)


class ResponseProcessor:
    """Renders response templates using caller-supplied Python logic.

    The custom logic is executed with a restricted set of globals; the
    variables it defines are interpolated into the selected template.
    """

    def __init__(self):
        self.response_templates: Dict[str, str] = {
            'user': "{'id': user_id, 'name': 'Test User'}",
            'product': "{'sku': product_id, 'price': 19.99}",
        }
        self.sandbox_globals = {
            'json': json,
            'len': len,
            'str': str,
            'int': int,
        }

    async def process_response(self, template_type: str, custom_logic: str) -> Any:
        """Execute ``custom_logic`` and render the matching template.

        Returns the rendered template parsed as JSON, or an error
        dictionary if execution, rendering or parsing fails.
        """
        template = self.response_templates.get(template_type, '{}')
        try:
            locals_dict: Dict[str, Any] = {}
            exec(custom_logic, self.sandbox_globals, locals_dict)
            processed = eval(f"f'''{template}'''", self.sandbox_globals, locals_dict)
            return json.loads(processed)
        except Exception as e:
            return {'error': str(e)}


processor = ResponseProcessor()


@app.route('/', methods=['GET'])
async def index():
    return """
    <form action="/api" method="post">
        <h2>API Response Generator</h2>
        Template Type:
        <select name="template_type">
            <option value="user">User</option>
            <option value="product">Product</option>
        </select><br>
        Custom Logic (Python):<br>
        <textarea name="custom_logic" rows=6 cols=50>
user_id = 42
product_id = 'XJ-209'
        </textarea><br>
        <button type="submit">Generate Response</button>
    </form>
    """


@app.route('/api', methods=['POST'])
async def api_handler():
    form = await request.form
    result = await processor.process_response(
        form['template_type'],
        form['custom_logic'],
    )
    return jsonify(result)


@app.route('/debug', methods=['GET'])
async def debug():
    endpoints = [str(rule) for rule in app.url_map.iter_rules()]
    return jsonify({'status': 'active', 'endpoints': endpoints})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
