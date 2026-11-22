import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict

from quart import Quart, request, jsonify

app = Quart(__name__)


class TemplateType(str, Enum):
    USER = 'user'
    PRODUCT = 'product'


@dataclass
class TemplateVariables:
    user_id: int = 0
    product_id: str = ''


def _user_template(variables: TemplateVariables) -> Dict[str, Any]:
    return {'id': variables.user_id, 'name': 'Test User'}


def _product_template(variables: TemplateVariables) -> Dict[str, Any]:
    return {'sku': variables.product_id, 'price': 19.99}


def _error(message: str) -> Dict[str, Any]:
    return {'error': message}


class ResponseProcessor:

    def __init__(self):
        self.response_templates: Dict[TemplateType, Callable[[TemplateVariables], Dict[str, Any]]] = {
            TemplateType.USER: _user_template,
            TemplateType.PRODUCT: _product_template,
        }

    @staticmethod
    def _parse_variables(variables_json: str) -> TemplateVariables:
        vars_dict = json.loads(variables_json)
        return TemplateVariables(
            user_id=int(vars_dict.get('user_id', 0)),
            product_id=str(vars_dict.get('product_id', '')),
        )

    async def process_response(self, template_type: TemplateType, variables_json: str) -> Dict[str, Any]:
        try:
            variables = self._parse_variables(variables_json)
            template = self.response_templates.get(template_type)
            if not template:
                return _error('Invalid template type')
            return template(variables)
        except json.JSONDecodeError as e:
            return _error(f'Invalid JSON: {str(e)}')
        except ValueError as e:
            return _error(f'Invalid value: {str(e)}')
        except Exception as e:
            return _error(f'Processing failed: {str(e)}')


processor = ResponseProcessor()

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
    '{\n'
    '    "user_id": 42,\n'
    '    "product_id": "XJ-209"\n'
    '}\n'
    '        </textarea><br>\n'
    '        <button type="submit">Generate Response</button>\n'
    '    </form>\n    '
)


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
    app.run(host='0.0.0.0', port=5000)
