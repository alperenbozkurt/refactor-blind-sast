"""API response generator service.

Refactored into helpers, named constants and a small config object.
Behaviour, module-level names, signatures, routes and the CLI are unchanged.
"""

from quart import Quart, request, jsonify
import asyncio  # noqa: F401  (kept to preserve the original module namespace)
import inspect  # noqa: F401  (kept to preserve the original module namespace)
from typing import Dict, Any
import json
from dataclasses import dataclass

app = Quart(__name__)

# --- Response templates -----------------------------------------------------
USER_TEMPLATE = "{'id': user_id, 'name': 'Test User'}"
PRODUCT_TEMPLATE = "{'sku': product_id, 'price': 19.99}"
DEFAULT_TEMPLATE = '{}'

# --- Debug endpoint ---------------------------------------------------------
DEBUG_STATUS = 'active'

# --- Index page markup (returned verbatim) ----------------------------------
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


@dataclass(frozen=True)
class ServerConfig:
    """Network settings used when the module is run as a script."""

    host: str = '0.0.0.0'
    port: int = 5000


DEFAULT_SERVER_CONFIG = ServerConfig()


def _build_response_templates() -> Dict[str, str]:
    """Return a fresh mapping of template type -> template source."""
    return {'user': USER_TEMPLATE, 'product': PRODUCT_TEMPLATE}


def _build_sandbox_globals() -> Dict[str, Any]:
    """Return a fresh globals mapping used to exec/eval custom logic."""
    return {'json': json, 'len': len, 'str': str, 'int': int}


class ResponseProcessor:
    """Renders JSON responses from a template plus user-supplied logic."""

    def __init__(self):
        self.response_templates: Dict[str, str] = _build_response_templates()
        self.sandbox_globals: Dict[str, Any] = _build_sandbox_globals()

    async def process_response(self, template_type: str, custom_logic: str) -> Any:
        template = self.response_templates.get(template_type, DEFAULT_TEMPLATE)
        try:
            locals_dict = self._execute_custom_logic(custom_logic)
            processed = self._render_template(template, locals_dict)
            return json.loads(processed)
        except Exception as e:
            return {'error': str(e)}

    def _execute_custom_logic(self, custom_logic: str) -> Dict[str, Any]:
        """Run the user-supplied code and capture its local variables."""
        locals_dict: Dict[str, Any] = {}
        exec(custom_logic, self.sandbox_globals, locals_dict)
        return locals_dict

    def _render_template(self, template: str, locals_dict: Dict[str, Any]) -> str:
        """Interpolate the template with the captured local variables."""
        return eval(f"f'''{template}'''", self.sandbox_globals, locals_dict)


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
    return jsonify({'status': DEBUG_STATUS, 'endpoints': [str(rule) for rule in app.url_map.iter_rules()]})


def main(config: ServerConfig = DEFAULT_SERVER_CONFIG) -> None:
    """Entry point for ``python <module>``; serves the Quart app."""
    app.run(host=config.host, port=config.port)


if __name__ == '__main__':
    main()
