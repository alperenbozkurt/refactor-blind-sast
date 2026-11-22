"""Quart application that generates JSON API responses from named templates."""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List

from quart import Quart, jsonify, request

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServerConfig:
    """Host/port binding for the development server."""

    host: str = '0.0.0.0'
    port: int = 5000


SERVER_CONFIG = ServerConfig()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_USER_ID = 0
DEFAULT_PRODUCT_ID = ''

USER_DISPLAY_NAME = 'Test User'
PRODUCT_PRICE = 19.99

DEBUG_STATUS = 'active'

FORM_TEMPLATE_TYPE_FIELD = 'template_type'
FORM_VARIABLES_JSON_FIELD = 'variables_json'

ERROR_INVALID_TEMPLATE = 'Invalid template type'

INDEX_HTML = '''
    <form action="/api" method="post">
        <h2>API Response Generator</h2>
        Template Type:
        <select name="template_type">
            <option value="user">User</option>
            <option value="product">Product</option>
        </select><br>
        Variables (JSON):<br>
        <textarea name="variables_json" rows=6 cols=50>
{
    "user_id": 42,
    "product_id": "XJ-209"
}
        </textarea><br>
        <button type="submit">Generate Response</button>
    </form>
    '''

app = Quart(__name__)


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


class TemplateType(str, Enum):
    USER = 'user'
    PRODUCT = 'product'


@dataclass
class TemplateVariables:
    user_id: int = DEFAULT_USER_ID
    product_id: str = DEFAULT_PRODUCT_ID


TemplateRenderer = Callable[[TemplateVariables], Dict[str, Any]]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _error_payload(message: str) -> Dict[str, Any]:
    """Build the standard error response body."""
    return {'error': message}


def _registered_endpoints() -> List[str]:
    """Return the string form of every rule in the URL map."""
    return [str(rule) for rule in app.url_map.iter_rules()]


# ---------------------------------------------------------------------------
# Response processing
# ---------------------------------------------------------------------------


class ResponseProcessor:
    """Renders response payloads from templates and JSON-encoded variables."""

    def __init__(self):
        self.response_templates: Dict[TemplateType, TemplateRenderer] = {
            TemplateType.USER: self._render_user_template,
            TemplateType.PRODUCT: self._render_product_template,
        }

    async def process_response(self, template_type: TemplateType, variables_json: str) -> Dict[str, Any]:
        try:
            variables = self._parse_variables(variables_json)
            template = self.response_templates.get(template_type)
            if not template:
                return _error_payload(ERROR_INVALID_TEMPLATE)
            return template(variables)
        except json.JSONDecodeError as e:
            return _error_payload(f'Invalid JSON: {str(e)}')
        except ValueError as e:
            return _error_payload(f'Invalid value: {str(e)}')
        except Exception as e:
            return _error_payload(f'Processing failed: {str(e)}')

    @staticmethod
    def _parse_variables(variables_json: str) -> TemplateVariables:
        """Decode the JSON payload into a ``TemplateVariables`` instance."""
        variables_dict = json.loads(variables_json)
        return TemplateVariables(
            user_id=int(variables_dict.get('user_id', DEFAULT_USER_ID)),
            product_id=str(variables_dict.get('product_id', DEFAULT_PRODUCT_ID)),
        )

    @staticmethod
    def _render_user_template(variables: TemplateVariables) -> Dict[str, Any]:
        return {'id': variables.user_id, 'name': USER_DISPLAY_NAME}

    @staticmethod
    def _render_product_template(variables: TemplateVariables) -> Dict[str, Any]:
        return {'sku': variables.product_id, 'price': PRODUCT_PRICE}


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
    try:
        template_type = TemplateType(form[FORM_TEMPLATE_TYPE_FIELD])
        result = await processor.process_response(template_type, form[FORM_VARIABLES_JSON_FIELD])
        return jsonify(result)
    except ValueError as e:
        return jsonify(_error_payload(f'Invalid template type: {str(e)}'))


@app.route('/debug', methods=['GET'])
async def debug():
    return jsonify({'status': DEBUG_STATUS, 'endpoints': _registered_endpoints()})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the development server."""
    app.run(host=SERVER_CONFIG.host, port=SERVER_CONFIG.port)


if __name__ == '__main__':
    main()
