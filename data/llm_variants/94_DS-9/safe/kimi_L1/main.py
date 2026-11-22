"""Falcon web application that evaluates simple comparison rules."""

import datetime
import json
import operator
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

import falcon
from falcon import Request, Response


class Operator(str, Enum):
    GREATER_THAN = '>'
    LESS_THAN = '<'
    EQUALS = '=='
    GREATER_EQUAL = '>='
    LESS_EQUAL = '<='
    NOT_EQUAL = '!='


@dataclass
class Rule:
    field: str
    operator: Operator
    value: Any


class RuleEngine:
    """Stores named rules and evaluates them against input data."""

    def __init__(self):
        self.rules: Dict[str, Rule] = {}

    def evaluate_rule(self, rule_name: str, rule_config: str, data: dict) -> Any:
        """Parse and store ``rule_config`` under ``rule_name``, then evaluate it."""
        comparisons = {
            Operator.GREATER_THAN: operator.gt,
            Operator.LESS_THAN: operator.lt,
            Operator.EQUALS: operator.eq,
            Operator.GREATER_EQUAL: operator.ge,
            Operator.LESS_EQUAL: operator.le,
            Operator.NOT_EQUAL: operator.ne,
        }
        try:
            config = json.loads(rule_config)
            rule = Rule(
                field=config['field'],
                operator=Operator(config['operator']),
                value=config['value'],
            )
            self.rules[rule_name] = rule
            field_value = data.get(rule.field)
            compare = comparisons.get(rule.operator)
            if compare is None:
                return False
            return compare(field_value, rule.value)
        except json.JSONDecodeError as exc:
            return {'error': f'Invalid rule configuration: {str(exc)}'}
        except KeyError as exc:
            return {'error': f'Missing required field: {str(exc)}'}
        except ValueError as exc:
            return {'error': f'Invalid operator: {str(exc)}'}
        except Exception as exc:
            return {'error': f'Evaluation failed: {str(exc)}'}


engine = RuleEngine()


class RuleResource:
    """Handles rule evaluation requests sent to POST /evaluate."""

    def on_post(self, req: Request, resp: Response):
        try:
            body = json.loads(req.stream.read())
            result = engine.evaluate_rule(
                body['rule_name'],
                body['rule_config'],
                body.get('data', {}),
            )
            resp.media = {'result': result}
        except json.JSONDecodeError as exc:
            resp.media = {'error': f'Invalid JSON: {str(exc)}'}
            resp.status = falcon.HTTP_400
        except Exception as exc:
            resp.media = {'error': str(exc)}
            resp.status = falcon.HTTP_400


class IndexResource:
    """Serves the HTML front page for the rule evaluation engine."""

    def on_get(self, req: Request, resp: Response):
        resp.content_type = 'text/html'
        resp.text = (
            '\n'
            '        <html>\n'
            '            <head><title>Rule Evaluation Engine</title></head>\n'
            '            <body>\n'
            '                <h1>Rule Evaluation Engine</h1>\n'
            '                <form action="/evaluate" method="post">\n'
            '                    Rule Name: <input type="text" name="rule_name" required><br>\n'
            '                    Rule Configuration (JSON):<br>\n'
            '                    <textarea name="rule_config" rows=4 cols=50 required>\n'
            '{\n'
            '    "field": "value",\n'
            '    "operator": ">",\n'
            '    "value": 100\n'
            '}\n'
            '                    </textarea><br>\n'
            '                    Input Data (JSON):<br>\n'
            '                    <textarea name="data" rows=4 cols=50 required>\n'
            '{"value": 150}\n'
            '                    </textarea><br>\n'
            '                    <button type="submit">Evaluate</button>\n'
            '                </form>\n'
            '                <h2>Stored Rules:</h2>\n'
            '                <pre id="rules"></pre>\n'
            '                <script>\n'
            "                    fetch('/rules').then(r => r.json()).then(data => {\n"
            "                        document.getElementById('rules').innerText = JSON.stringify(data, null, 2);\n"
            '                    });\n'
            '                </script>\n'
            '            </body>\n'
            '        </html>\n'
            '        '
        )


class RulesResource:
    """Returns the currently stored rules as JSON."""

    def on_get(self, req: Request, resp: Response):
        resp.media = {name: vars(rule) for name, rule in engine.rules.items()}


app = falcon.App()
app.add_route('/', IndexResource())
app.add_route('/evaluate', RuleResource())
app.add_route('/rules', RulesResource())


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000)
