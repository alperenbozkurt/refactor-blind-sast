"""Minimal aiohttp service for applying transformation rules to JSON data."""

import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from aiohttp import web
import aiohttp_jinja2
import jinja2

routes = web.RouteTableDef()

_TEMPLATES_DIR = 'templates'
_INDEX_TEMPLATE_PATH = os.path.join(_TEMPLATES_DIR, 'index.html')

_DEFAULT_INDEX_HTML = """
            <!DOCTYPE html>
            <html>
            <head><title>Data Transformer</title></head>
            <body>
                <h1>Data Transformation Service</h1>
                <form id="transformForm">
                    <h3>Input Data (JSON):</h3>
                    <textarea name="data" rows=4 cols=50 required>{"sample": "data", "price": 10}</textarea><br>
                    <h3>Transformation Rule (JSON):</h3>
                    <textarea name="rule_config" rows=6 cols=50 required>
{
    "type": "uppercase",
    "field": "sample"
}
                    </textarea><br>
                    <div style="color: #666; font-size: 0.9em;">
                        Available transformations: uppercase, lowercase, numeric_multiply, string_length
                    </div>
                    <button type="submit">Transform</button>
                </form>
                <h3>Result:</h3>
                <pre id="result"></pre>
                <script>
                    document.getElementById('transformForm').addEventListener('submit', async (e) => {
                        e.preventDefault();
                        const response = await fetch('/transform', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                data: JSON.parse(e.target.data.value),
                                rule_config: e.target.rule_config.value
                            })
                        });
                        document.getElementById('result').innerText = JSON.stringify(await response.json(), null, 2);
                    });
                </script>
                <h3>Stored Transformations:</h3>
                <pre id="transformations"></pre>
                <script>
                    fetch('/transformations').then(r => r.json()).then(data => {
                        document.getElementById('transformations').innerText = JSON.stringify(data, null, 2);
                    });
                </script>
            </body>
            </html>
            """


class TransformationType(str, Enum):
    """Supported transformation kinds."""

    UPPERCASE = 'uppercase'
    LOWERCASE = 'lowercase'
    NUMERIC_MULTIPLY = 'numeric_multiply'
    STRING_LENGTH = 'string_length'


@dataclass
class TransformationRule:
    """A single transformation rule parsed from a rule configuration."""

    type: TransformationType
    field: str
    multiplier: float = 1.0


class DataTransformer:
    """Applies transformation rules to dictionaries and records applied rules."""

    def __init__(self):
        self.transformations: Dict[str, TransformationRule] = {}

    async def transform(self, data: Any, rule_config: str) -> Any:
        try:
            rule = self._parse_rule(rule_config)
            if not isinstance(data, dict):
                return {'error': 'Input data must be a dictionary'}
            if rule.field not in data:
                return {'error': f'Field {rule.field} not found in data'}
            error = self._apply_rule(data, rule)
            if error is not None:
                return {'error': error}
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

    @staticmethod
    def _parse_rule(rule_config: str) -> TransformationRule:
        config = json.loads(rule_config)
        return TransformationRule(
            type=TransformationType(config['type']),
            field=config['field'],
            multiplier=float(config.get('multiplier', 1.0)),
        )

    @staticmethod
    def _apply_rule(data: Dict[str, Any], rule: TransformationRule) -> Optional[str]:
        """Apply ``rule`` to ``data`` in place; return an error message on failure."""
        value = data[rule.field]
        if rule.type == TransformationType.UPPERCASE:
            if not isinstance(value, str):
                return 'Uppercase transformation requires string value'
            data[rule.field] = value.upper()
        elif rule.type == TransformationType.LOWERCASE:
            if not isinstance(value, str):
                return 'Lowercase transformation requires string value'
            data[rule.field] = value.lower()
        elif rule.type == TransformationType.NUMERIC_MULTIPLY:
            if not isinstance(value, (int, float)):
                return 'Numeric multiply requires numeric value'
            data[rule.field] = value * rule.multiplier
        elif rule.type == TransformationType.STRING_LENGTH:
            if not isinstance(value, str):
                return 'String length requires string value'
            data[rule.field] = len(value)
        return None


transformer = DataTransformer()


@routes.get('/')
@aiohttp_jinja2.template('index.html')
async def index(request: web.Request) -> Dict[str, Any]:
    return {'transformations': transformer.transformations}


@routes.post('/transform')
async def transform_data(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return web.json_response({'error': 'Invalid JSON'}, status=400)
    result = await transformer.transform(payload.get('data'), payload.get('rule_config'))
    return web.json_response({'result': result})


@routes.get('/transformations')
async def get_transformations(request: web.Request) -> web.Response:
    return web.json_response({
        field: vars(rule)
        for field, rule in transformer.transformations.items()
    })


async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))
    _ensure_default_template()
    return app


def _ensure_default_template() -> None:
    if not os.path.exists(_TEMPLATES_DIR):
        os.makedirs(_TEMPLATES_DIR)
    if not os.path.exists(_INDEX_TEMPLATE_PATH):
        with open(_INDEX_TEMPLATE_PATH, 'w') as f:
            f.write(_DEFAULT_INDEX_HTML)


if __name__ == '__main__':
    web.run_app(init_app(), port=8080)
