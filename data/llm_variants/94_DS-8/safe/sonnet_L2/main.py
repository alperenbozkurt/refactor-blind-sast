from dataclasses import dataclass
from enum import Enum
import json
from typing import Any, Callable, Dict

from quart import Quart, request, jsonify

app = Quart(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

DEFAULT_USER_ID = 0
DEFAULT_PRODUCT_ID = ''
DEFAULT_USER_NAME = 'Test User'
DEFAULT_PRODUCT_PRICE = 19.99

ERROR_KEY = 'error'
ERROR_INVALID_TEMPLATE = 'Invalid template type'

INDEX_HTML = (
    '\n    <form action="/api" method="post">\n'
    '        <h2>API Response Generator</h2>\n'
    '        Template Type:\n'
    '        <select name="template_type">\n'
    '            <option value="user">User</option>\n'
    '            <option value="product">Product</option>\n'
    '        </select><br>\n'
    '        Variables (JSON):<br>\n'
    '        <textarea name="variables_json" rows=6 cols=50>\n'
    '{\n    "user_id": 42,\n    "product_id": "XJ-209"\n}\n'
    '        </textarea><br>\n'
    '        <button type="submit">Generate Response</button>\n'
    '    </form>\n    '
)


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #

class TemplateType(str, Enum):
    USER = 'user'
    PRODUCT = 'product'


@dataclass
class TemplateVariables:
    user_id: int = DEFAULT_USER_ID
    product_id: str = DEFAULT_PRODUCT_ID


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _error(message: str) -> Dict[str, Any]:
    """Build an error payload."""
    return {ERROR_KEY: message}


def _build_user_response(variables: TemplateVariables) -> Dict[str, Any]:
    return {'id': variables.user_id, 'name': DEFAULT_USER_NAME}


def _build_product_response(variables: TemplateVariables) -> Dict[str, Any]:
    return {'sku': variables.product_id, 'price': DEFAULT_PRODUCT_PRICE}


def _parse_variables(variables_json: str) -> TemplateVariables:
    """Parse a JSON string into TemplateVariables.

    May raise json.JSONDecodeError, ValueError or other exceptions, which
    are handled by the caller.
    """
    vars_dict = json.loads(variables_json)
    return TemplateVariables(
        user_id=int(vars_dict.get('user_id', DEFAULT_USER_ID)),
        product_id=str(vars_dict.get('product_id', DEFAULT_PRODUCT_ID)),
    )


# --------------------------------------------------------------------------- #
# Processor
# --------------------------------------------------------------------------- #

class ResponseProcessor:

    def __init__(self):
        self.response_templates: Dict[
            TemplateType, Callable[[TemplateVariables], Dict[str, Any]]
        ] = {
            TemplateType.USER: _build_user_response,
            TemplateType.PRODUCT: _build_product_response,
        }

    async def process_response(self, template_type: TemplateType, variables_json: str) -> Dict[str, Any]:
        try:
            variables = _parse_variables(variables_json)
            template = self.response_templates.get(template_type)
            if not template:
                return _error(ERROR_INVALID_TEMPLATE)
            return template(variables)
        except json.JSONDecodeError as e:
            return _error(f'Invalid JSON: {str(e)}')
        except ValueError as e:
            return _error(f'Invalid value: {str(e)}')
        except Exception as e:
            return _error(f'Processing failed: {str(e)}')


processor = ResponseProcessor()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.route('/', methods=['GET'])
async def index():
    return INDEX_HTML


@app.route('/api', methods=['POST'])
async def api_handler():
    form = await request.form
    try:
        template_type = TemplateType(form['template_type'])
        result = await processor.process_response(template_type, form['variables_json'])
        return jsonify(result)
    except ValueError as e:
        return jsonify(_error(f'Invalid template type: {str(e)}'))


@app.route('/debug', methods=['GET'])
async def debug():
    return jsonify({
        'status': 'active',
        'endpoints': [str(rule) for rule in app.url_map.iter_rules()],
    })


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT)
