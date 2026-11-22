from quart import Quart, request, jsonify
import asyncio
import inspect
from typing import Dict, Any
import json

# ---------------------------------------------------------------------------
# Constants / configuration
# ---------------------------------------------------------------------------

DEFAULT_TEMPLATE = '{}'
DEFAULT_RESPONSE_TEMPLATES: Dict[str, str] = {
    'user': "{'id': user_id, 'name': 'Test User'}",
    'product': "{'sku': product_id, 'price': 19.99}",
}

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

INDEX_HTML = (
    '\n    <form action="/api" method="post">\n'
    '        <h2>API Response Generator</h2>\n'
    '        Template Type:\n'
    '        <select name="template_type">\n'
    '            <option value="user">User</option>\n'
    '            <option value="product">Product</option>\n'
    '        </select><br>\n'
    '        Custom Logic (Python):<br>\n'
    '        <textarea name="custom_logic" rows=6 cols=50>\n'
    "user_id = 42\n"
    "product_id = 'XJ-209'\n"
    '        </textarea><br>\n'
    '        <button type="submit">Generate Response</button>\n'
    '    </form>\n    '
)

app = Quart(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_sandbox_globals() -> Dict[str, Any]:
    """Return the globals namespace made available to custom logic.

    NOTE: This is not a real sandbox. Executing user-supplied code with
    exec/eval allows arbitrary code execution; this behavior is preserved
    as-is from the original module and should be replaced (and the endpoint
    protected) before any real-world deployment.
    """
    return {'json': json, 'len': len, 'str': str, 'int': int}


def _build_template_expression(template: str) -> str:
    """Wrap a template in an f-string expression suitable for eval()."""
    return f"f'''{template}'''"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

class ResponseProcessor:

    def __init__(self):
        self.response_templates: Dict[str, str] = dict(DEFAULT_RESPONSE_TEMPLATES)
        self.sandbox_globals = _build_sandbox_globals()

    def _get_template(self, template_type: str) -> str:
        return self.response_templates.get(template_type, DEFAULT_TEMPLATE)

    def _run_custom_logic(self, custom_logic: str) -> Dict[str, Any]:
        locals_dict: Dict[str, Any] = {}
        exec(custom_logic, self.sandbox_globals, locals_dict)
        return locals_dict

    def _render_template(self, template: str, locals_dict: Dict[str, Any]) -> str:
        return eval(_build_template_expression(template), self.sandbox_globals, locals_dict)

    async def process_response(self, template_type: str, custom_logic: str) -> Any:
        template = self._get_template(template_type)
        try:
            locals_dict = self._run_custom_logic(custom_logic)
            processed = self._render_template(template, locals_dict)
            return json.loads(processed)
        except Exception as e:
            return {'error': str(e)}


processor = ResponseProcessor()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

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


def main():
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
