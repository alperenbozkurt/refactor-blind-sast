from aiohttp import web
import aiohttp_jinja2
import jinja2
import os
import json
from typing import Any, Callable, Dict, Tuple, Type, Union
from enum import Enum
from dataclasses import dataclass

routes = web.RouteTableDef()

TEMPLATES_DIR = 'templates'
INDEX_TEMPLATE_PATH = 'templates/index.html'

INDEX_TEMPLATE_HTML = '\n            <!DOCTYPE html>\n            <html>\n            <head><title>Data Transformer</title></head>\n            <body>\n                <h1>Data Transformation Service</h1>\n                <form id="transformForm">\n                    <h3>Input Data (JSON):</h3>\n                    <textarea name="data" rows=4 cols=50 required>{"sample": "data", "price": 10}</textarea><br>\n                    <h3>Transformation Rule (JSON):</h3>\n                    <textarea name="rule_config" rows=6 cols=50 required>\n{\n    "type": "uppercase",\n    "field": "sample"\n}\n                    </textarea><br>\n                    <div style="color: #666; font-size: 0.9em;">\n                        Available transformations: uppercase, lowercase, numeric_multiply, string_length\n                    </div>\n                    <button type="submit">Transform</button>\n                </form>\n                <h3>Result:</h3>\n                <pre id="result"></pre>\n                <script>\n                    document.getElementById(\'transformForm\').addEventListener(\'submit\', async (e) => {\n                        e.preventDefault();\n                        const response = await fetch(\'/transform\', {\n                            method: \'POST\',\n                            headers: {\'Content-Type\': \'application/json\'},\n                            body: JSON.stringify({\n                                data: JSON.parse(e.target.data.value),\n                                rule_config: e.target.rule_config.value\n                            })\n                        });\n                        document.getElementById(\'result\').innerText = JSON.stringify(await response.json(), null, 2);\n                    });\n                </script>\n                <h3>Stored Transformations:</h3>\n                <pre id="transformations"></pre>\n                <script>\n                    fetch(\'/transformations\').then(r => r.json()).then(data => {\n                        document.getElementById(\'transformations\').innerText = JSON.stringify(data, null, 2);\n                    });\n                </script>\n            </body>\n            </html>\n            '


class TransformationType(str, Enum):
    UPPERCASE = 'uppercase'
    LOWERCASE = 'lowercase'
    NUMERIC_MULTIPLY = 'numeric_multiply'
    STRING_LENGTH = 'string_length'


@dataclass
class TransformationRule:
    type: TransformationType
    field: str
    multiplier: float = 1.0


# For each transformation type: (accepted value types, transform function, error message
# used when the value has an unsupported type).
_TransformSpec = Tuple[
    Union[Type, Tuple[Type, ...]],
    Callable[[Any, TransformationRule], Any],
    str,
]

_TRANSFORM_SPECS: Dict[TransformationType, _TransformSpec] = {
    TransformationType.UPPERCASE: (
        str,
        lambda value, rule: value.upper(),
        'Uppercase transformation requires string value',
    ),
    TransformationType.LOWERCASE: (
        str,
        lambda value, rule: value.lower(),
        'Lowercase transformation requires string value',
    ),
    TransformationType.NUMERIC_MULTIPLY: (
        (int, float),
        lambda value, rule: value * rule.multiplier,
        'Numeric multiply requires numeric value',
    ),
    TransformationType.STRING_LENGTH: (
        str,
        lambda value, rule: len(value),
        'String length requires string value',
    ),
}


def _parse_rule(rule_config: str) -> TransformationRule:
    """Build a TransformationRule from its JSON configuration string."""
    config = json.loads(rule_config)
    return TransformationRule(
        type=TransformationType(config['type']),
        field=config['field'],
        multiplier=float(config.get('multiplier', 1.0)),
    )


class DataTransformer:

    def __init__(self):
        self.transformations: Dict[str, TransformationRule] = {}

    async def transform(self, data: Any, rule_config: str) -> Any:
        try:
            rule = _parse_rule(rule_config)

            if not isinstance(data, dict):
                return {'error': 'Input data must be a dictionary'}
            if rule.field not in data:
                return {'error': f'Field {rule.field} not found in data'}

            value = data[rule.field]
            accepted_types, apply_transform, type_error = _TRANSFORM_SPECS[rule.type]
            if not isinstance(value, accepted_types):
                return {'error': type_error}

            data[rule.field] = apply_transform(value, rule)
            self.transformations[rule.field] = rule
            return data
        except json.JSONDecodeError as e:
            return {'error': f'Invalid rule configuration: {str(e)}'}
        except ValueError as e:
            return {'error': f'Invalid value: {str(e)}'}
        except KeyError as e:
            return {'error': f'Missing required field: {str(e)}'}
        except Exception as e:
            return {'error': f'Transformation failed: {str(e)}'}


transformer = DataTransformer()


@routes.get('/')
@aiohttp_jinja2.template('index.html')
async def index(request: web.Request) -> Dict[str, Any]:
    return {'transformations': transformer.transformations}


@routes.post('/transform')
async def transform_data(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
        result = await transformer.transform(payload.get('data'), payload.get('rule_config'))
        return web.json_response({'result': result})
    except json.JSONDecodeError:
        return web.json_response({'error': 'Invalid JSON'}, status=400)


@routes.get('/transformations')
async def get_transformations(request: web.Request) -> web.Response:
    return web.json_response({name: vars(rule) for name, rule in transformer.transformations.items()})


def _ensure_index_template() -> None:
    """Create the templates directory and default index template if missing."""
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    if not os.path.exists(INDEX_TEMPLATE_PATH):
        with open(INDEX_TEMPLATE_PATH, 'w') as f:
            f.write(INDEX_TEMPLATE_HTML)


async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))
    _ensure_index_template()
    return app


if __name__ == '__main__':
    web.run_app(init_app(), port=8080)
