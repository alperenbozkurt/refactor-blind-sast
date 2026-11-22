"""JSON data transformation web service.

An aiohttp application exposing endpoints that apply configurable
transformations (uppercase, lowercase, numeric multiply, string length)
to fields of a JSON object, while keeping a registry of applied rules.
"""

import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple

import aiohttp_jinja2
import jinja2
from aiohttp import web

# ---------------------------------------------------------------------------
# Server and routing configuration
# ---------------------------------------------------------------------------

ROUTE_INDEX = '/'
ROUTE_TRANSFORM = '/transform'
ROUTE_TRANSFORMATIONS = '/transformations'

SERVER_PORT = 8080
HTTP_STATUS_BAD_REQUEST = 400

TEMPLATE_DIRECTORY = 'templates'
INDEX_TEMPLATE_NAME = 'index.html'

DEFAULT_MULTIPLIER = 1.0

# ---------------------------------------------------------------------------
# Error messages
# ---------------------------------------------------------------------------

ERROR_INVALID_JSON = 'Invalid JSON'
ERROR_INPUT_NOT_DICT = 'Input data must be a dictionary'
ERROR_UPPERCASE_REQUIRES_STRING = 'Uppercase transformation requires string value'
ERROR_LOWERCASE_REQUIRES_STRING = 'Lowercase transformation requires string value'
ERROR_NUMERIC_MULTIPLY_REQUIRES_NUMBER = 'Numeric multiply requires numeric value'
ERROR_STRING_LENGTH_REQUIRES_STRING = 'String length requires string value'

routes = web.RouteTableDef()


def _error_dict(message: str) -> Dict[str, str]:
    """Build the standard error payload returned by the service."""
    return {'error': message}


class TransformationType(str, Enum):
    UPPERCASE = 'uppercase'
    LOWERCASE = 'lowercase'
    NUMERIC_MULTIPLY = 'numeric_multiply'
    STRING_LENGTH = 'string_length'


@dataclass
class TransformationRule:
    type: TransformationType
    field: str
    multiplier: float = DEFAULT_MULTIPLIER


# Outcome of applying a rule to a value: (new value, error message).
# Exactly one of the two items is None.
TransformOutcome = Tuple[Any, Optional[str]]


def _apply_uppercase(value: Any, rule: TransformationRule) -> TransformOutcome:
    if isinstance(value, str):
        return value.upper(), None
    return None, ERROR_UPPERCASE_REQUIRES_STRING


def _apply_lowercase(value: Any, rule: TransformationRule) -> TransformOutcome:
    if isinstance(value, str):
        return value.lower(), None
    return None, ERROR_LOWERCASE_REQUIRES_STRING


def _apply_numeric_multiply(value: Any, rule: TransformationRule) -> TransformOutcome:
    if isinstance(value, (int, float)):
        return value * rule.multiplier, None
    return None, ERROR_NUMERIC_MULTIPLY_REQUIRES_NUMBER


def _apply_string_length(value: Any, rule: TransformationRule) -> TransformOutcome:
    if isinstance(value, str):
        return len(value), None
    return None, ERROR_STRING_LENGTH_REQUIRES_STRING


_TRANSFORMATION_HANDLERS: Dict[
    TransformationType, Callable[[Any, TransformationRule], TransformOutcome]
] = {
    TransformationType.UPPERCASE: _apply_uppercase,
    TransformationType.LOWERCASE: _apply_lowercase,
    TransformationType.NUMERIC_MULTIPLY: _apply_numeric_multiply,
    TransformationType.STRING_LENGTH: _apply_string_length,
}


class DataTransformer:
    """Applies transformation rules to dictionary payloads.

    Successfully applied rules are stored in ``transformations``, keyed by
    the name of the field they were applied to.
    """

    def __init__(self):
        self.transformations: Dict[str, TransformationRule] = {}

    async def transform(self, data: Any, rule_config: str) -> Any:
        try:
            rule = self._parse_rule(rule_config)
            error = self._validate_input(data, rule)
            if error is not None:
                return error
            return self._apply_rule(data, rule)
        except json.JSONDecodeError as e:
            return _error_dict(f'Invalid rule configuration: {str(e)}')
        except ValueError as e:
            return _error_dict(f'Invalid value: {str(e)}')
        except KeyError as e:
            return _error_dict(f'Missing required field: {str(e)}')
        except Exception as e:
            return _error_dict(f'Transformation failed: {str(e)}')

    @staticmethod
    def _parse_rule(rule_config: str) -> TransformationRule:
        """Deserialize a JSON rule configuration into a TransformationRule."""
        config = json.loads(rule_config)
        return TransformationRule(
            type=TransformationType(config['type']),
            field=config['field'],
            multiplier=float(config.get('multiplier', DEFAULT_MULTIPLIER)),
        )

    @staticmethod
    def _validate_input(data: Any, rule: TransformationRule) -> Optional[Dict[str, str]]:
        """Return an error payload if the rule cannot be applied, else None."""
        if not isinstance(data, dict):
            return _error_dict(ERROR_INPUT_NOT_DICT)
        if rule.field not in data:
            return _error_dict(f'Field {rule.field} not found in data')
        return None

    def _apply_rule(self, data: Dict[str, Any], rule: TransformationRule) -> Any:
        """Apply the rule to the data in place and register it on success."""
        new_value, error = _TRANSFORMATION_HANDLERS[rule.type](data[rule.field], rule)
        if error is not None:
            return _error_dict(error)
        data[rule.field] = new_value
        self.transformations[rule.field] = rule
        return data


transformer = DataTransformer()


@routes.get(ROUTE_INDEX)
@aiohttp_jinja2.template(INDEX_TEMPLATE_NAME)
async def index(request: web.Request) -> Dict[str, Any]:
    return {'transformations': transformer.transformations}


@routes.post(ROUTE_TRANSFORM)
async def transform_data(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
        result = await transformer.transform(payload.get('data'), payload.get('rule_config'))
        return web.json_response({'result': result})
    except json.JSONDecodeError:
        return web.json_response(_error_dict(ERROR_INVALID_JSON), status=HTTP_STATUS_BAD_REQUEST)


@routes.get(ROUTE_TRANSFORMATIONS)
async def get_transformations(request: web.Request) -> web.Response:
    return web.json_response({k: vars(v) for (k, v) in transformer.transformations.items()})


# ---------------------------------------------------------------------------
# Default front-end template
# ---------------------------------------------------------------------------

INDEX_TEMPLATE_CONTENT = """
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


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

def _ensure_directory(path: str) -> None:
    """Create the directory at *path* if it does not already exist."""
    if not os.path.exists(path):
        os.makedirs(path)


def _ensure_file(path: str, content: str) -> None:
    """Write *content* to *path* if the file does not already exist."""
    if not os.path.exists(path):
        with open(path, 'w') as f:
            f.write(content)


def _ensure_default_templates() -> None:
    """Create the templates directory and default index template if missing."""
    _ensure_directory(TEMPLATE_DIRECTORY)
    _ensure_file(os.path.join(TEMPLATE_DIRECTORY, INDEX_TEMPLATE_NAME), INDEX_TEMPLATE_CONTENT)


def _configure_templating(app: web.Application) -> None:
    """Wire aiohttp_jinja2 into the app and bootstrap default templates."""
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))
    _ensure_default_templates()


async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    _configure_templating(app)
    return app


def main() -> None:
    web.run_app(init_app(), port=SERVER_PORT)


if __name__ == '__main__':
    main()
