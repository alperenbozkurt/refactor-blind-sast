import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Tuple

import aiohttp_jinja2
import jinja2
from aiohttp import web

routes = web.RouteTableDef()


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


_VALUE_REQUIREMENTS: Dict[TransformationType, Tuple[Any, str]] = {
    TransformationType.UPPERCASE: (str, 'Uppercase transformation requires string value'),
    TransformationType.LOWERCASE: (str, 'Lowercase transformation requires string value'),
    TransformationType.NUMERIC_MULTIPLY: ((int, float), 'Numeric multiply requires numeric value'),
    TransformationType.STRING_LENGTH: (str, 'String length requires string value'),
}

_VALUE_TRANSFORMS: Dict[TransformationType, Callable[[Any, TransformationRule], Any]] = {
    TransformationType.UPPERCASE: lambda value, rule: value.upper(),
    TransformationType.LOWERCASE: lambda value, rule: value.lower(),
    TransformationType.NUMERIC_MULTIPLY: lambda value, rule: value * rule.multiplier,
    TransformationType.STRING_LENGTH: lambda value, rule: len(value),
}


def _build_rule(rule_config: str) -> TransformationRule:
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
            rule = _build_rule(rule_config)
            if not isinstance(data, dict):
                return {'error': 'Input data must be a dictionary'}
            if rule.field not in data:
                return {'error': f'Field {rule.field} not found in data'}
            value = data[rule.field]
            expected_types, requirement_error = _VALUE_REQUIREMENTS[rule.type]
            if not isinstance(value, expected_types):
                return {'error': requirement_error}
            data[rule.field] = _VALUE_TRANSFORMS[rule.type](value, rule)
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
    return web.json_response({k: vars(v) for (k, v) in transformer.transformations.items()})


INDEX_HTML = """
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


async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))
    if not os.path.exists('templates'):
        os.makedirs('templates')
    if not os.path.exists('templates/index.html'):
        with open('templates/index.html', 'w') as f:
            f.write(INDEX_HTML)
    return app


if __name__ == '__main__':
    web.run_app(init_app(), port=8080)
