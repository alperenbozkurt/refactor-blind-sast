import falcon
import json
import datetime
from falcon import Request, Response
from enum import Enum
from typing import Dict, Any, Callable
from dataclasses import dataclass
from operator import gt, lt, eq, ge, le, ne

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

ROUTE_INDEX = '/'
ROUTE_EVALUATE = '/evaluate'
ROUTE_RULES = '/rules'

HTML_CONTENT_TYPE = 'text/html'

INDEX_HTML = '\n        <html>\n            <head><title>Rule Evaluation Engine</title></head>\n            <body>\n                <h1>Rule Evaluation Engine</h1>\n                <form action="/evaluate" method="post">\n                    Rule Name: <input type="text" name="rule_name" required><br>\n                    Rule Configuration (JSON):<br>\n                    <textarea name="rule_config" rows=4 cols=50 required>\n{\n    "field": "value",\n    "operator": ">",\n    "value": 100\n}\n                    </textarea><br>\n                    Input Data (JSON):<br>\n                    <textarea name="data" rows=4 cols=50 required>\n{"value": 150}\n                    </textarea><br>\n                    <button type="submit">Evaluate</button>\n                </form>\n                <h2>Stored Rules:</h2>\n                <pre id="rules"></pre>\n                <script>\n                    fetch(\'/rules\').then(r => r.json()).then(data => {\n                        document.getElementById(\'rules\').innerText = JSON.stringify(data, null, 2);\n                    });\n                </script>\n            </body>\n        </html>\n        '


# --------------------------------------------------------------------------- #
# Domain model
# --------------------------------------------------------------------------- #

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


OPERATOR_FUNCTIONS: Dict[Operator, Callable[[Any, Any], Any]] = {
    Operator.GREATER_THAN: gt,
    Operator.LESS_THAN: lt,
    Operator.EQUALS: eq,
    Operator.GREATER_EQUAL: ge,
    Operator.LESS_EQUAL: le,
    Operator.NOT_EQUAL: ne,
}


def _error(message: str) -> Dict[str, str]:
    """Build an error payload."""
    return {'error': message}


def _parse_rule(rule_config: str) -> Rule:
    """Parse a JSON rule configuration into a Rule."""
    config = json.loads(rule_config)
    return Rule(
        field=config['field'],
        operator=Operator(config['operator']),
        value=config['value'],
    )


def _apply_rule(rule: Rule, data: dict) -> Any:
    """Apply a rule to the given data."""
    field_value = data.get(rule.field)
    compare = OPERATOR_FUNCTIONS.get(rule.operator)
    if compare is None:
        return False
    return compare(field_value, rule.value)


class RuleEngine:

    def __init__(self):
        self.rules: Dict[str, Rule] = {}

    def evaluate_rule(self, rule_name: str, rule_config: str, data: dict) -> Any:
        try:
            rule = _parse_rule(rule_config)
            self.rules[rule_name] = rule
            return _apply_rule(rule, data)
        except json.JSONDecodeError as e:
            return _error(f'Invalid rule configuration: {str(e)}')
        except KeyError as e:
            return _error(f'Missing required field: {str(e)}')
        except ValueError as e:
            return _error(f'Invalid operator: {str(e)}')
        except Exception as e:
            return _error(f'Evaluation failed: {str(e)}')


engine = RuleEngine()


# --------------------------------------------------------------------------- #
# HTTP resources
# --------------------------------------------------------------------------- #

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
            resp.media = _error(f'Invalid JSON: {str(e)}')
            resp.status = falcon.HTTP_400
        except Exception as e:
            resp.media = _error(str(e))
            resp.status = falcon.HTTP_400


class IndexResource:

    def on_get(self, req: Request, resp: Response):
        resp.content_type = HTML_CONTENT_TYPE
        resp.text = INDEX_HTML


class RulesResource:

    def on_get(self, req: Request, resp: Response):
        resp.media = {name: vars(rule) for (name, rule) in engine.rules.items()}


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #

def create_app() -> falcon.App:
    """Create the Falcon application and register all routes."""
    application = falcon.App()
    application.add_route(ROUTE_INDEX, IndexResource())
    application.add_route(ROUTE_EVALUATE, RuleResource())
    application.add_route(ROUTE_RULES, RulesResource())
    return application


app = create_app()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
