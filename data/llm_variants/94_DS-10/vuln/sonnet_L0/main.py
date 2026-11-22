from aiohttp import web
import aiohttp_jinja2
import jinja2
import os
import json
from typing import Dict, Any

routes = web.RouteTableDef()

TEMPLATES_DIR = 'templates'
INDEX_TEMPLATE_PATH = 'templates/index.html'

INDEX_TEMPLATE = """
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


class DataTransformer:

    def __init__(self):
        self.transformations: Dict[str, str] = {}
        self.sandbox = {
            '__builtins__': None,
            'json': json,
            'str': str,
            'float': float,
            'int': int,
        }

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


def _ensure_index_template() -> None:
    if not os.path.exists(TEMPLATES_DIR):
        os.makedirs(TEMPLATES_DIR)
    if not os.path.exists(INDEX_TEMPLATE_PATH):
        with open(INDEX_TEMPLATE_PATH, 'w') as f:
            f.write(INDEX_TEMPLATE)


async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    aiohttp_jinja2.setup(
        app, loader=jinja2.FileSystemLoader(os.path.dirname(__file__))
    )
    _ensure_index_template()
    return app


if __name__ == '__main__':
    web.run_app(init_app(), port=8080)
