import falcon
import json
import datetime
from falcon import Request, Response

# ---------------------------------------------------------------------------
# Constants / configuration
# ---------------------------------------------------------------------------

HOST = '0.0.0.0'
PORT = 8000

ROUTE_INDEX = '/'
ROUTE_EVALUATE = '/evaluate'
ROUTE_RULES = '/rules'

CONTENT_TYPE_HTML = 'text/html'

KEY_RULE_NAME = 'rule_name'
KEY_RULE_EXPRESSION = 'rule_expression'
KEY_DATA = 'data'
KEY_RESULT = 'result'
KEY_ERROR = 'error'

INDEX_HTML = (
    '\n        <html>\n            <head><title>Rule Evaluation Engine</title></head>\n'
    '            <body>\n                <h1>Rule Evaluation Engine</h1>\n'
    '                <form action="/evaluate" method="post">\n'
    '                    Rule Name: <input type="text" name="rule_name"><br>\n'
    '                    Rule Expression (Python):<br>\n'
    '                    <textarea name="rule_expression" rows=4 cols=50>\n'
    'data.get(\'value\', 0) > 100\n                    </textarea><br>\n'
    '                    Input Data (JSON):<br>\n'
    '                    <textarea name="data" rows=4 cols=50>\n'
    '{"value": 150}\n                    </textarea><br>\n'
    '                    <button type="submit">Evaluate</button>\n'
    '                </form>\n                <h2>Stored Rules:</h2>\n'
    '                <pre id="rules"></pre>\n                <script>\n'
    '                    fetch(\'/rules\').then(r => r.json()).then(data => {\n'
    '                        document.getElementById(\'rules\').innerText = '
    'JSON.stringify(data, null, 2);\n                    });\n'
    '                </script>\n            </body>\n        </html>\n        '
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_payload(exc: Exception) -> dict:
    """Build the standard error payload for an exception."""
    return {KEY_ERROR: str(exc)}


def _build_safe_globals() -> dict:
    """Create the globals mapping exposed to rule expressions.

    NOTE: this is not a real sandbox; rule expressions are executed with
    ``exec`` and must only come from trusted sources.
    """
    return {'datetime': datetime, 'min': min, 'max': max, 'sum': sum}


def _read_json_body(req: Request):
    """Parse the request stream as JSON."""
    return json.loads(req.stream.read())


# ---------------------------------------------------------------------------
# Domain logic
# ---------------------------------------------------------------------------

class RuleEngine:

    def __init__(self):
        self.rules = {}
        self.safe_globals = _build_safe_globals()

    def evaluate_rule(self, rule_name: str, rule_expression: str, data: dict):
        try:
            result = self._execute(rule_expression, data)
            self.rules[rule_name] = rule_expression
            return result
        except Exception as e:
            return _error_payload(e)

    def _execute(self, rule_expression: str, data: dict):
        """Run the expression and return the value bound to ``result``."""
        locals_dict = {'data': data}
        exec(f'result = {rule_expression}', self.safe_globals, locals_dict)
        return locals_dict.get('result')


engine = RuleEngine()


# ---------------------------------------------------------------------------
# HTTP resources
# ---------------------------------------------------------------------------

class RuleResource:

    def on_post(self, req: Request, resp: Response):
        try:
            body = _read_json_body(req)
            result = engine.evaluate_rule(
                body[KEY_RULE_NAME],
                body[KEY_RULE_EXPRESSION],
                body.get(KEY_DATA, {}),
            )
            resp.media = {KEY_RESULT: result}
        except Exception as e:
            resp.media = _error_payload(e)
            resp.status = falcon.HTTP_400


class IndexResource:

    def on_get(self, req: Request, resp: Response):
        resp.content_type = CONTENT_TYPE_HTML
        resp.text = INDEX_HTML


class RulesResource:

    def on_get(self, req: Request, resp: Response):
        resp.media = engine.rules


# ---------------------------------------------------------------------------
# Application wiring
# ---------------------------------------------------------------------------

def _register_routes(application: falcon.App) -> None:
    application.add_route(ROUTE_INDEX, IndexResource())
    application.add_route(ROUTE_EVALUATE, RuleResource())
    application.add_route(ROUTE_RULES, RulesResource())


def _create_app() -> falcon.App:
    application = falcon.App()
    _register_routes(application)
    return application


app = _create_app()


def _main() -> None:
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == '__main__':
    _main()
