import asyncio
import inspect
import json
from typing import Any, Dict

from quart import Quart, jsonify, request

app = Quart(__name__)

INDEX_HTML = (
    '\n'
    '    <form action="/api" method="post">\n'
    '        <h2>API Response Generator</h2>\n'
    '        Template Type:\n'
    '        <select name="template_type">\n'
    '            <option value="user">User</option>\n'
    '            <option value="product">Product</option>\n'
    '        </select><br>\n'
    '        Custom Logic (Python):<br>\n'
    '        <textarea name="custom_logic" rows=6 cols=50>\n'
    'user_id = 42\n'
    "product_id = 'XJ-209'\n"
    '        </textarea><br>\n'
    '        <button type="submit">Generate Response</button>\n'
    '    </form>\n'
    '    '
)


class ResponseProcessor:
    """Builds JSON responses from templates combined with custom logic."""

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
        template = self.response_templates.get(template_type, '{}')
        try:
            locals_dict = {}
            exec(custom_logic, self.sandbox_globals, locals_dict)
            processed = eval(f"f'''{template}'''", self.sandbox_globals, locals_dict)
            return json.loads(processed)
        except Exception as e:
            return {'error': str(e)}


processor = ResponseProcessor()


@app.route('/', methods=['GET'])
async def index():
    return INDEX_HTML


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
    return jsonify({
        'status': 'active',
        'endpoints': [str(rule) for rule in app.url_map.iter_rules()],
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
