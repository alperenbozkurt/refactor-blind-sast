"""Rule evaluation engine exposed as a Falcon web service.

The service stores named comparison rules and evaluates them against
caller-supplied JSON data. It serves a small HTML UI on the index route,
a JSON evaluation endpoint, and an endpoint listing the stored rules.
"""

import datetime
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict

import falcon
from falcon import Request, Response

CONTENT_TYPE_HTML = 'text/html'

ROUTE_INDEX = '/'
ROUTE_EVALUATE = '/evaluate'
ROUTE_RULES = '/rules'

INDEX_HTML = """
        <html>
            <head><title>Rule Evaluation Engine</title></head>
            <body>
                <h1>Rule Evaluation Engine</h1>
                <form action="/evaluate" method="post">
                    Rule Name: <input type="text" name="rule_name" required><br>
                    Rule Configuration (JSON):<br>
                    <textarea name="rule_config" rows=4 cols=50 required>
{
    "field": "value",
    "operator": ">",
    "value": 100
}
                    </textarea><br>
                    Input Data (JSON):<br>
                    <textarea name="data" rows=4 cols=50 required>
{"value": 150}
                    </textarea><br>
                    <button type="submit">Evaluate</button>
                </form>
                <h2>Stored Rules:</h2>
                <pre id="rules"></pre>
                <script>
                    fetch('/rules').then(r => r.json()).then(data => {
                        document.getElementById('rules').innerText = JSON.stringify(data, null, 2);
                    });
                </script>
            </body>
        </html>
        """


def _error_payload(message: str) -> Dict[str, str]:
    """Build the JSON-serialisable body used for error responses."""
    return {'error': message}


def _respond_with_error(resp: Response, message: str) -> None:
    """Attach an error payload to the response and mark it as a bad request."""
    resp.media = _error_payload(message)
    resp.status = falcon.HTTP_400


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


@dataclass(frozen=True)
class ServerConfig:
    """Settings used when running the module as a script."""

    host: str = '0.0.0.0'
    port: int = 8000


class RuleEngine:
    """Parses, stores and evaluates named rules."""

    _OPERATIONS: Dict[Operator, Callable[[Any, Any], bool]] = {
        Operator.GREATER_THAN: lambda field_value, value: field_value > value,
        Operator.LESS_THAN: lambda field_value, value: field_value < value,
        Operator.EQUALS: lambda field_value, value: field_value == value,
        Operator.GREATER_EQUAL: lambda field_value, value: field_value >= value,
        Operator.LESS_EQUAL: lambda field_value, value: field_value <= value,
        Operator.NOT_EQUAL: lambda field_value, value: field_value != value,
    }

    def __init__(self):
        self.rules: Dict[str, Rule] = {}

    def evaluate_rule(self, rule_name: str, rule_config: str, data: dict) -> Any:
        try:
            rule = self._parse_rule(rule_config)
            self.rules[rule_name] = rule
            return self._apply(rule, data)
        except json.JSONDecodeError as e:
            return _error_payload(f'Invalid rule configuration: {str(e)}')
        except KeyError as e:
            return _error_payload(f'Missing required field: {str(e)}')
        except ValueError as e:
            return _error_payload(f'Invalid operator: {str(e)}')
        except Exception as e:
            return _error_payload(f'Evaluation failed: {str(e)}')

    @staticmethod
    def _parse_rule(rule_config: str) -> Rule:
        """Deserialise a JSON rule configuration into a :class:`Rule`."""
        config = json.loads(rule_config)
        return Rule(
            field=config['field'],
            operator=Operator(config['operator']),
            value=config['value'],
        )

    def _apply(self, rule: Rule, data: dict) -> bool:
        """Evaluate *rule* against *data* using its comparison operator."""
        operation = self._OPERATIONS.get(rule.operator)
        if operation is None:
            return False
        field_value = data.get(rule.field)
        return operation(field_value, rule.value)


engine = RuleEngine()


class RuleResource:
    """Evaluates rules submitted via HTTP POST."""

    def on_post(self, req: Request, resp: Response):
        try:
            body = json.loads(req.stream.read())
            result = engine.evaluate_rule(body['rule_name'], body['rule_config'], body.get('data', {}))
            resp.media = {'result': result}
        except json.JSONDecodeError as e:
            _respond_with_error(resp, f'Invalid JSON: {str(e)}')
        except Exception as e:
            _respond_with_error(resp, str(e))


class IndexResource:
    """Serves the HTML front page."""

    def on_get(self, req: Request, resp: Response):
        resp.content_type = CONTENT_TYPE_HTML
        resp.text = INDEX_HTML


class RulesResource:
    """Lists the rules currently stored by the engine."""

    def on_get(self, req: Request, resp: Response):
        resp.media = {name: vars(rule) for (name, rule) in engine.rules.items()}


def create_app() -> falcon.App:
    """Build the Falcon application and register all routes."""
    application = falcon.App()
    application.add_route(ROUTE_INDEX, IndexResource())
    application.add_route(ROUTE_EVALUATE, RuleResource())
    application.add_route(ROUTE_RULES, RulesResource())
    return application


app = create_app()


def main() -> None:
    """Run the application with the development server."""
    import uvicorn

    config = ServerConfig()
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == '__main__':
    main()
