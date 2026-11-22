import falcon
import json
import datetime
import operator as _op
from falcon import Request, Response
from enum import Enum
from typing import Dict, Any
from dataclasses import dataclass


class Operator(str, Enum):
    GREATER_THAN = '>'
    LESS_THAN = '<'
    EQUALS = '=='
    GREATER_EQUAL = '>='
    LESS_EQUAL = '<='
    NOT_EQUAL = '!='


_OPERATIONS = {
    Operator.GREATER_THAN: _op.gt,
    Operator.LESS_THAN: _op.lt,
    Operator.EQUALS: _op.eq,
    Operator.GREATER_EQUAL: _op.ge,
    Operator.LESS_EQUAL: _op.le,
    Operator.NOT_EQUAL: _op.ne,
}


@dataclass
class Rule:
    field: str
    operator: Operator
    value: Any


class RuleEngine:

    def __init__(self):
        self.rules: Dict[str, Rule] = {}

    def evaluate_rule(self, rule_name: str, rule_config: str, data: dict) -> Any:
        try:
            config = json.loads(rule_config)
            rule = Rule(
                field=config['field'],
                operator=Operator(config['operator']),
                value=config['value'],
            )
            self.rules[rule_name] = rule

            field_value = data.get(rule.field)
            compare = _OPERATIONS.get(rule.operator)
            if compare is None:
                return False
            return compare(field_value, rule.value)
        except json.JSONDecodeError as e:
            return {'error': f'Invalid rule configuration: {str(e)}'}
        except KeyError as e:
            return {'error': f'Missing required field: {str(e)}'}
        except ValueError as e:
            return {'error': f'Invalid operator: {str(e)}'}
        except Exception as e:
            return {'error': f'Evaluation failed: {str(e)}'}


engine = RuleEngine()


class RuleResource:

    def on_post(self, req: Request, resp: Response):
        try:
            body = json.loads(req.stream.read())
            result = engine.evaluate_rule(
                body['rule_name'],
                body['rule_config'],
                body.get('data', {}),
            )
            resp.media = {'result': result}
        except json.JSONDecodeError as e:
            resp.media = {'error': f'Invalid JSON: {str(e)}'}
            resp.status = falcon.HTTP_400
        except Exception as e:
            resp.media = {'error': str(e)}
            resp.status = falcon.HTTP_400


class IndexResource:

    def on_get(self, req: Request, resp: Response):
        resp.content_type = 'text/html'
        resp.text = '\n        <html>\n            <head><title>Rule Evaluation Engine</title></head>\n            <body>\n                <h1>Rule Evaluation Engine</h1>\n                <form action="/evaluate" method="post">\n                    Rule Name: <input type="text" name="rule_name" required><br>\n                    Rule Configuration (JSON):<br>\n                    <textarea name="rule_config" rows=4 cols=50 required>\n{\n    "field": "value",\n    "operator": ">",\n    "value": 100\n}\n                    </textarea><br>\n                    Input Data (JSON):<br>\n                    <textarea name="data" rows=4 cols=50 required>\n{"value": 150}\n                    </textarea><br>\n                    <button type="submit">Evaluate</button>\n                </form>\n                <h2>Stored Rules:</h2>\n                <pre id="rules"></pre>\n                <script>\n                    fetch(\'/rules\').then(r => r.json()).then(data => {\n                        document.getElementById(\'rules\').innerText = JSON.stringify(data, null, 2);\n                    });\n                </script>\n            </body>\n        </html>\n        '


class RulesResource:

    def on_get(self, req: Request, resp: Response):
        resp.media = {name: vars(rule) for name, rule in engine.rules.items()}


app = falcon.App()
app.add_route('/', IndexResource())
app.add_route('/evaluate', RuleResource())
app.add_route('/rules', RulesResource())

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
