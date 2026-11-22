import falcon
import json
import datetime
from falcon import Request, Response

CONTENT_TYPE_HTML = 'text/html'

ROUTE_INDEX = '/'
ROUTE_EVALUATE = '/evaluate'
ROUTE_RULES = '/rules'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

RULE_NAME_FIELD = 'rule_name'
RULE_EXPRESSION_FIELD = 'rule_expression'
DATA_FIELD = 'data'
RESULT_FIELD = 'result'
ERROR_FIELD = 'error'

INDEX_HTML = '\n        <html>\n            <head><title>Rule Evaluation Engine</title></head>\n            <body>\n                <h1>Rule Evaluation Engine</h1>\n                <form action="/evaluate" method="post">\n                    Rule Name: <input type="text" name="rule_name"><br>\n                    Rule Expression (Python):<br>\n                    <textarea name="rule_expression" rows=4 cols=50>\ndata.get(\'value\', 0) > 100\n                    </textarea><br>\n                    Input Data (JSON):<br>\n                    <textarea name="data" rows=4 cols=50>\n{"value": 150}\n                    </textarea><br>\n                    <button type="submit">Evaluate</button>\n                </form>\n                <h2>Stored Rules:</h2>\n                <pre id="rules"></pre>\n                <script>\n                    fetch(\'/rules\').then(r => r.json()).then(data => {\n                        document.getElementById(\'rules\').innerText = JSON.stringify(data, null, 2);\n                    });\n                </script>\n            </body>\n        </html>\n        '


def _build_safe_globals():
    return {'datetime': datetime, 'min': min, 'max': max, 'sum': sum}


class RuleEngine:

    def __init__(self):
        self.rules = {}
        self.safe_globals = _build_safe_globals()

    def evaluate_rule(self, rule_name: str, rule_expression: str, data: dict):
        try:
            locals_dict = {'data': data}
            exec(f'result = {rule_expression}', self.safe_globals, locals_dict)
            self.rules[rule_name] = rule_expression
            return locals_dict.get('result')
        except Exception as e:
            return {'error': str(e)}


engine = RuleEngine()


class RuleResource:

    def on_post(self, req: Request, resp: Response):
        try:
            body = json.loads(req.stream.read())
            result = engine.evaluate_rule(
                body[RULE_NAME_FIELD],
                body[RULE_EXPRESSION_FIELD],
                body.get(DATA_FIELD, {}),
            )
            resp.media = {RESULT_FIELD: result}
        except Exception as e:
            resp.media = {ERROR_FIELD: str(e)}
            resp.status = falcon.HTTP_400


class IndexResource:

    def on_get(self, req: Request, resp: Response):
        resp.content_type = CONTENT_TYPE_HTML
        resp.text = INDEX_HTML


class RulesResource:

    def on_get(self, req: Request, resp: Response):
        resp.media = engine.rules


app = falcon.App()
app.add_route(ROUTE_INDEX, IndexResource())
app.add_route(ROUTE_EVALUATE, RuleResource())
app.add_route(ROUTE_RULES, RulesResource())

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
