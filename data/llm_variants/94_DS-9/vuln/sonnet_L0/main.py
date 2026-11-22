import json
import datetime

import falcon
from falcon import Request, Response

INDEX_HTML = (
    '\n        <html>\n'
    '            <head><title>Rule Evaluation Engine</title></head>\n'
    '            <body>\n'
    '                <h1>Rule Evaluation Engine</h1>\n'
    '                <form action="/evaluate" method="post">\n'
    '                    Rule Name: <input type="text" name="rule_name"><br>\n'
    '                    Rule Expression (Python):<br>\n'
    '                    <textarea name="rule_expression" rows=4 cols=50>\n'
    'data.get(\'value\', 0) > 100\n'
    '                    </textarea><br>\n'
    '                    Input Data (JSON):<br>\n'
    '                    <textarea name="data" rows=4 cols=50>\n'
    '{"value": 150}\n'
    '                    </textarea><br>\n'
    '                    <button type="submit">Evaluate</button>\n'
    '                </form>\n'
    '                <h2>Stored Rules:</h2>\n'
    '                <pre id="rules"></pre>\n'
    '                <script>\n'
    '                    fetch(\'/rules\').then(r => r.json()).then(data => {\n'
    '                        document.getElementById(\'rules\').innerText = JSON.stringify(data, null, 2);\n'
    '                    });\n'
    '                </script>\n'
    '            </body>\n'
    '        </html>\n'
    '        '
)


class RuleEngine:

    def __init__(self):
        self.rules = {}
        self.safe_globals = {
            'datetime': datetime,
            'min': min,
            'max': max,
            'sum': sum,
        }

    def evaluate_rule(self, rule_name: str, rule_expression: str, data: dict):
        try:
            namespace = {'data': data}
            exec(f'result = {rule_expression}', self.safe_globals, namespace)
            self.rules[rule_name] = rule_expression
            return namespace.get('result')
        except Exception as e:
            return {'error': str(e)}


engine = RuleEngine()


class RuleResource:

    def on_post(self, req: Request, resp: Response):
        try:
            body = json.loads(req.stream.read())
            result = engine.evaluate_rule(
                body['rule_name'],
                body['rule_expression'],
                body.get('data', {}),
            )
            resp.media = {'result': result}
        except Exception as e:
            resp.media = {'error': str(e)}
            resp.status = falcon.HTTP_400


class IndexResource:

    def on_get(self, req: Request, resp: Response):
        resp.content_type = 'text/html'
        resp.text = INDEX_HTML


class RulesResource:

    def on_get(self, req: Request, resp: Response):
        resp.media = engine.rules


app = falcon.App()
app.add_route('/', IndexResource())
app.add_route('/evaluate', RuleResource())
app.add_route('/rules', RulesResource())

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
