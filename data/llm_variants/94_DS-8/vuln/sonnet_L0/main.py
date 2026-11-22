from quart import Quart, request, jsonify
import asyncio  # noqa: F401  (kept to preserve module-level names)
import inspect  # noqa: F401  (kept to preserve module-level names)
from typing import Dict, Any
import json

app = Quart(__name__)

DEFAULT_TEMPLATE = '{}'

INDEX_HTML = '''
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
    '''


class ResponseProcessor:
    # WARNING: this class executes caller-supplied code with exec()/eval().
    # That is inherently unsafe; behaviour is preserved here intentionally.

    def __init__(self):
        self.response_templates: Dict[str, str] = {
            'user': "{'id': user_id, 'name': 'Test User'}",
            'product': "{'sku': product_id, 'price': 19.99}",
        }
        self.sandbox_globals = {'json': json, 'len': len, 'str': str, 'int': int}

    def _render(self, template: str, custom_logic: str) -> str:
        local_vars: Dict[str, Any] = {}
        exec(custom_logic, self.sandbox_globals, local_vars)
        return eval(f"f'''{template}'''", self.sandbox_globals, local_vars)

    async def process_response(self, template_type: str, custom_logic: str) -> Any:
        template = self.response_templates.get(template_type, DEFAULT_TEMPLATE)
        try:
            return json.loads(self._render(template, custom_logic))
        except Exception as e:
            return {'error': str(e)}


processor = ResponseProcessor()


@app.route('/', methods=['GET'])
async def index():
    return INDEX_HTML


@app.route('/api', methods=['POST'])
async def api_handler():
    form = await request.form
    result = await processor.process_response(form['template_type'], form['custom_logic'])
    return jsonify(result)


@app.route('/debug', methods=['GET'])
async def debug():
    return jsonify({
        'status': 'active',
        'endpoints': [str(rule) for rule in app.url_map.iter_rules()],
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
