from aiohttp import web
import aiohttp_jinja2
import jinja2
import os
import json
from typing import Dict, Any

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

TEMPLATES_DIR = 'templates'
INDEX_TEMPLATE_PATH = 'templates/index.html'
DEFAULT_PORT = 8080

TRANSFORM_INPUT_NAME = 'data'
TRANSFORM_RESULT_NAME = 'result'

INDEX_TEMPLATE_CONTENT = '\n            <!DOCTYPE html>\n            <html>\n            <head><title>Data Transformer</title></head>\n            <body>\n                <h1>Data Transformation Service</h1>\n                <form id="transformForm">\n                    <textarea name="data" rows=4 cols=50>{"sample": "data"}</textarea><br>\n                    <textarea name="transform_code" rows=6 cols=50>\nresult = {k: v.upper() for k, v in data.items() if isinstance(v, str)}\n                    </textarea><br>\n                    <button type="submit">Transform</button>\n                </form>\n                <pre id="result"></pre>\n                <script>\n                    document.getElementById(\'transformForm\').addEventListener(\'submit\', async (e) => {\n                        e.preventDefault();\n                        const response = await fetch(\'/transform\', {\n                            method: \'POST\',\n                            headers: {\'Content-Type\': \'application/json\'},\n                            body: JSON.stringify({\n                                data: JSON.parse(e.target.data.value),\n                                transform_code: e.target.transform_code.value\n                            })\n                        });\n                        document.getElementById(\'result\').innerText = JSON.stringify(await response.json(), null, 2);\n                    });\n                </script>\n            </body>\n            </html>\n            '

routes = web.RouteTableDef()


# --------------------------------------------------------------------------- #
# Transformation logic
# --------------------------------------------------------------------------- #

def _build_sandbox() -> Dict[str, Any]:
    """Create the globals mapping used when executing transformation code."""
    return {
        '__builtins__': None,
        'json': json,
        'str': str,
        'float': float,
        'int': int,
    }


def _error_payload(exc: Exception) -> Dict[str, str]:
    """Build the error payload returned when a transformation fails."""
    return {'error': f'Transformation failed: {str(exc)}'}


class DataTransformer:

    def __init__(self):
        self.transformations: Dict[str, str] = {}
        self.sandbox = _build_sandbox()

    async def transform(self, data: Any, transform_code: str) -> Any:
        try:
            locals_dict = {TRANSFORM_INPUT_NAME: data}
            exec(transform_code, self.sandbox, locals_dict)
            return locals_dict.get(TRANSFORM_RESULT_NAME)
        except Exception as e:
            return _error_payload(e)


transformer = DataTransformer()


# --------------------------------------------------------------------------- #
# Route handlers
# --------------------------------------------------------------------------- #

@routes.get('/')
@aiohttp_jinja2.template('index.html')
async def index(request: web.Request) -> Dict[str, Any]:
    return {'transformations': transformer.transformations}


@routes.post('/transform')
async def transform_data(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
        result = await transformer.transform(
            payload.get('data'), payload.get('transform_code')
        )
        return web.json_response({'result': result})
    except json.JSONDecodeError:
        return web.json_response({'error': 'Invalid JSON'}, status=400)


@routes.get('/transformations')
async def get_transformations(request: web.Request) -> web.Response:
    return web.json_response(transformer.transformations)


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #

def _setup_templating(app: web.Application) -> None:
    """Configure the Jinja2 environment for the application."""
    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader(os.path.dirname(__file__))
    )


def _ensure_templates() -> None:
    """Make sure the templates directory and default index template exist."""
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    if not os.path.exists(INDEX_TEMPLATE_PATH):
        with open(INDEX_TEMPLATE_PATH, 'w') as f:
            f.write(INDEX_TEMPLATE_CONTENT)


async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    _setup_templating(app)
    _ensure_templates()
    return app


if __name__ == '__main__':
    web.run_app(init_app(), port=DEFAULT_PORT)
