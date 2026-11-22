"""Minimal aiohttp service for evaluating user-supplied data transformations."""

import json
import os
from typing import Any, Dict

import aiohttp_jinja2
import jinja2
from aiohttp import web

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8080

TEMPLATES_DIR = 'templates'
INDEX_TEMPLATE_NAME = 'index.html'
INDEX_TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, INDEX_TEMPLATE_NAME)

# Globals exposed to user-supplied transformation code.
SANDBOX_GLOBALS: Dict[str, Any] = {
    '__builtins__': None,
    'json': json,
    'str': str,
    'float': float,
    'int': int,
}

# Fallback page written when no index template exists yet.
DEFAULT_INDEX_HTML = """
            <!DOCTYPE html>
            <html>
            <head><title>Data Transformer</title></head>
            <body>
                <h1>Data Transformation Service</h1>
                <form id="transformForm">
                    <textarea name="data" rows=4 cols=50>{"sample": "data"}</textarea><br>
                    <textarea name="transform_code" rows=6 cols=50>
result = {k: v.upper() for k, v in data.items() if isinstance(v, str)}
                    </textarea><br>
                    <button type="submit">Transform</button>
                </form>
                <pre id="result"></pre>
                <script>
                    document.getElementById('transformForm').addEventListener('submit', async (e) => {
                        e.preventDefault();
                        const response = await fetch('/transform', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                data: JSON.parse(e.target.data.value),
                                transform_code: e.target.transform_code.value
                            })
                        });
                        document.getElementById('result').innerText = JSON.stringify(await response.json(), null, 2);
                    });
                </script>
            </body>
            </html>
            """

routes = web.RouteTableDef()


class DataTransformer:
    """Applies user-supplied transformation code within a restricted sandbox."""

    def __init__(self):
        self.transformations: Dict[str, str] = {}
        self.sandbox: Dict[str, Any] = dict(SANDBOX_GLOBALS)

    async def transform(self, data: Any, transform_code: str) -> Any:
        try:
            locals_dict = {'data': data}
            exec(transform_code, self.sandbox, locals_dict)
            return locals_dict.get('result')
        except Exception as e:
            return {'error': f'Transformation failed: {str(e)}'}


transformer = DataTransformer()


@routes.get('/')
@aiohttp_jinja2.template('index.html')
async def index(request: web.Request) -> Dict[str, Any]:
    """Render the index page with the registered transformations."""
    return {'transformations': transformer.transformations}


@routes.post('/transform')
async def transform_data(request: web.Request) -> web.Response:
    """Apply the posted transformation code to the posted data."""
    try:
        payload = await request.json()
        result = await transformer.transform(payload.get('data'), payload.get('transform_code'))
        return web.json_response({'result': result})
    except json.JSONDecodeError:
        return web.json_response({'error': 'Invalid JSON'}, status=400)


@routes.get('/transformations')
async def get_transformations(request: web.Request) -> web.Response:
    """Return the registered transformations as JSON."""
    return web.json_response(transformer.transformations)


def _configure_templates(app: web.Application) -> None:
    """Wire Jinja2 template rendering into the application."""
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))


def _ensure_templates_dir() -> None:
    """Create the templates directory if it does not exist."""
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)


def _ensure_index_template() -> None:
    """Write the default index template if none exists."""
    if not os.path.exists(INDEX_TEMPLATE_PATH):
        with open(INDEX_TEMPLATE_PATH, 'w') as f:
            f.write(DEFAULT_INDEX_HTML)


async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    _configure_templates(app)
    _ensure_templates_dir()
    _ensure_index_template()
    return app


if __name__ == '__main__':
    web.run_app(init_app(), port=DEFAULT_PORT)
