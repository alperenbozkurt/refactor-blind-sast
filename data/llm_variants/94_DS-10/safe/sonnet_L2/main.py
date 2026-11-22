from aiohttp import web
import aiohttp_jinja2
import jinja2
import os
import json
from typing import Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVER_PORT = 8080
TEMPLATES_DIR = 'templates'
INDEX_TEMPLATE_NAME = 'index.html'
INDEX_TEMPLATE_PATH = 'templates/index.html'

INDEX_TEMPLATE_CONTENT = '\n            <!DOCTYPE html>\n            <html>\n            <head><title>Data Transformer</title></head>\n            <body>\n                <h1>Data Transformation Service</h1>\n                <form id="transformForm">\n                    <h3>Input Data (JSON):</h3>\n                    <textarea name="data" rows=4 cols=50 required>{"sample": "data", "price": 10}</textarea><br>\n                    <h3>Transformation Rule (JSON):</h3>\n                    <textarea name="rule_config" rows=6 cols=50 required>\n{\n    "type": "uppercase",\n    "field": "sample"\n}\n                    </textarea><br>\n                    <div style="color: #666; font-size: 0.9em;">\n                        Available transformations: uppercase, lowercase, numeric_multiply, string_length\n                    </div>\n                    <button type="submit">Transform</button>\n                </form>\n                <h3>Result:</h3>\n                <pre id="result"></pre>\n                <script>\n                    document.getElementById(\'transformForm\').addEventListener(\'submit\', async (e) => {\n                        e.preventDefault();\n                        const response = await fetch(\'/transform\', {\n                            method: \'POST\',\n                            headers: {\'Content-Type\': \'application/json\'},\n                            body: JSON.stringify({\n                                data: JSON.parse(e.target.data.value),\n                                rule_config: e.target.rule_config.value\n                            })\n                        });\n                        document.getElementById(\'result\').innerText = JSON.stringify(await response.json(), null, 2);\n                    });\n                </script>\n                <h3>Stored Transformations:</h3>\n                <pre id="transformations"></pre>\n                <script>\n                    fetch(\'/transformations\').then(r => r.json()).then(data => {\n                        document.getElementById(\'transformations\').innerText = JSON.stringify(data, null, 2);\n                    });\n                </script>\n            </body>\n            </html>\n            '

routes = web.RouteTableDef()


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Transformation specifications
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _TransformationSpec:
    """Describes how a transformation validates and converts a value."""
    accepts: Callable[[Any], bool]
    apply: Callable[[Any, TransformationRule], Any]
    error_message: str


def _is_string(value: Any) -> bool:
    return isinstance(value, str)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float))


_TRANSFORMATION_SPECS: Dict[TransformationType, _TransformationSpec] = {
    TransformationType.UPPERCASE: _TransformationSpec(
        accepts=_is_string,
        apply=lambda value, rule: value.upper(),
        error_message='Uppercase transformation requires string value',
    ),
    TransformationType.LOWERCASE: _TransformationSpec(
        accepts=_is_string,
        apply=lambda value, rule: value.lower(),
        error_message='Lowercase transformation requires string value',
    ),
    TransformationType.NUMERIC_MULTIPLY: _TransformationSpec(
        accepts=_is_number,
        apply=lambda value, rule: value * rule.multiplier,
        error_message='Numeric multiply requires numeric value',
    ),
    TransformationType.STRING_LENGTH: _TransformationSpec(
        accepts=_is_string,
        apply=lambda value, rule: len(value),
        error_message='String length requires string value',
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(message: str) -> Dict[str, str]:
    return {'error': message}


def _parse_rule(rule_config: str) -> TransformationRule:
    config = json.loads(rule_config)
    return TransformationRule(
        type=TransformationType(config['type']),
        field=config['field'],
        multiplier=float(config.get('multiplier', 1.0)),
    )


# ---------------------------------------------------------------------------
# Transformer service
# ---------------------------------------------------------------------------

class DataTransformer:

    def __init__(self):
        self.transformations: Dict[str, TransformationRule] = {}

    async def transform(self, data: Any, rule_config: str) -> Any:
        try:
            rule = _parse_rule(rule_config)
            if not isinstance(data, dict):
                return _error('Input data must be a dictionary')
            if rule.field not in data:
                return _error(f'Field {rule.field} not found in data')
            spec = _TRANSFORMATION_SPECS[rule.type]
            value = data[rule.field]
            if not spec.accepts(value):
                return _error(spec.error_message)
            data[rule.field] = spec.apply(value, rule)
            self.transformations[rule.field] = rule
            return data
        except json.JSONDecodeError as e:
            return _error(f'Invalid rule configuration: {str(e)}')
        except ValueError as e:
            return _error(f'Invalid value: {str(e)}')
        except KeyError as e:
            return _error(f'Missing required field: {str(e)}')
        except Exception as e:
            return _error(f'Transformation failed: {str(e)}')


transformer = DataTransformer()


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@routes.get('/')
@aiohttp_jinja2.template(INDEX_TEMPLATE_NAME)
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
    return web.json_response({k: vars(v) for (k, v) in transformer.transformations.items()})


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

def _ensure_index_template() -> None:
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    if not os.path.exists(INDEX_TEMPLATE_PATH):
        with open(INDEX_TEMPLATE_PATH, 'w') as f:
            f.write(INDEX_TEMPLATE_CONTENT)


async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))
    _ensure_index_template()
    return app


if __name__ == '__main__':
    web.run_app(init_app(), port=SERVER_PORT)
