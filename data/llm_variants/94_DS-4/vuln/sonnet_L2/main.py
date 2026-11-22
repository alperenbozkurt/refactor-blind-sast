import ast
import math
import operator
import os
from typing import Any, Callable, Dict

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# --------------------------------------------------------------------------- #
# Constants / configuration
# --------------------------------------------------------------------------- #
TEMPLATES_DIR = 'templates'
FORM_TEMPLATE_NAME = 'form.html'
FORM_TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, FORM_TEMPLATE_NAME)

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

DEFAULT_BASE_PRICES = {'premium': 100, 'standard': 50, 'economy': 20}
UNKNOWN_PRODUCT_PRICE = 0

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_ERROR = 500
CALCULATION_ERROR_DETAIL = 'Calculation error'

MAX_EXPONENT = 10000

FORM_TEMPLATE_HTML = (
    '\n'
    '        <!DOCTYPE html>\n'
    '        <html>\n'
    '        <head><title>Dynamic Pricing Calculator</title></head>\n'
    '        <body>\n'
    '            <h1>Product Pricing Calculator</h1>\n'
    '            <form method="post" action="/calculate">\n'
    '                Product Type: \n'
    '                <select name="product_type">\n'
    '                    <option value="premium">Premium</option>\n'
    '                    <option value="standard">Standard</option>\n'
    '                    <option value="economy">Economy</option>\n'
    '                </select><br>\n'
    '                Quantity: <input type="number" name="quantity" min="1" value="1"><br>\n'
    '                Discount Logic (Python): \n'
    '                <input type="text" name="discount_logic" \n'
    '                       placeholder="e.g., math.log(quantity)*0.1" size="40"><br>\n'
    '                <button type="submit">Calculate</button>\n'
    '            </form>\n'
    '        </body>\n'
    '        </html>\n'
    '        '
)


# --------------------------------------------------------------------------- #
# Safe expression evaluation
#
# The discount logic is user-supplied. Passing it to eval() would allow
# arbitrary code execution on the server, so it is evaluated by a restricted
# AST walker that supports arithmetic, comparisons, conditionals, a few safe
# builtins, the ``quantity`` variable and public functions/constants of ``math``.
# --------------------------------------------------------------------------- #
_BINARY_OPERATORS: Dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS: Dict[type, Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_COMPARE_OPERATORS: Dict[type, Callable[[Any, Any], bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

_SAFE_BUILTINS: Dict[str, Callable[..., Any]] = {
    'abs': abs,
    'min': min,
    'max': max,
    'round': round,
    'pow': pow,
    'int': int,
    'float': float,
}


class SafeExpressionEvaluator:
    """Evaluate a restricted subset of Python expressions."""

    def __init__(self, variables: Dict[str, Any]):
        self.variables = variables

    def evaluate(self, expression: str) -> Any:
        tree = ast.parse(expression.strip(), mode='eval')
        return self._eval(tree.body)

    def _eval(self, node: ast.AST) -> Any:
        handler = getattr(self, '_eval_' + type(node).__name__, None)
        if handler is None:
            raise ValueError(f'Unsupported expression element: {type(node).__name__}')
        return handler(node)

    def _eval_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (int, float, bool)):
            return node.value
        raise ValueError('Only numeric constants are allowed')

    def _eval_Name(self, node: ast.Name) -> Any:
        if node.id in self.variables:
            return self.variables[node.id]
        if node.id in _SAFE_BUILTINS:
            return _SAFE_BUILTINS[node.id]
        raise ValueError(f"Name '{node.id}' is not allowed")

    def _eval_Attribute(self, node: ast.Attribute) -> Any:
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == 'math'
            and not node.attr.startswith('_')
            and hasattr(math, node.attr)
        ):
            return getattr(math, node.attr)
        raise ValueError('Only attributes of the math module are allowed')

    def _eval_BinOp(self, node: ast.BinOp) -> Any:
        op = _BINARY_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError('Unsupported operator')
        left = self._eval(node.left)
        right = self._eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise ValueError('Exponent too large')
        return op(left, right)

    def _eval_UnaryOp(self, node: ast.UnaryOp) -> Any:
        op = _UNARY_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError('Unsupported operator')
        return op(self._eval(node.operand))

    def _eval_BoolOp(self, node: ast.BoolOp) -> Any:
        is_and = isinstance(node.op, ast.And)
        result: Any = None
        for value_node in node.values:
            result = self._eval(value_node)
            if is_and and not result:
                return result
            if not is_and and result:
                return result
        return result

    def _eval_Compare(self, node: ast.Compare) -> bool:
        left = self._eval(node.left)
        for op_node, comparator in zip(node.ops, node.comparators):
            op = _COMPARE_OPERATORS.get(type(op_node))
            if op is None:
                raise ValueError('Unsupported comparison')
            right = self._eval(comparator)
            if not op(left, right):
                return False
            left = right
        return True

    def _eval_IfExp(self, node: ast.IfExp) -> Any:
        branch = node.body if self._eval(node.test) else node.orelse
        return self._eval(branch)

    def _eval_Call(self, node: ast.Call) -> Any:
        if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
            raise ValueError('Keyword and star arguments are not allowed')
        func = self._eval(node.func)
        if not callable(func):
            raise ValueError('Object is not callable')
        return func(*[self._eval(arg) for arg in node.args])


# --------------------------------------------------------------------------- #
# Domain logic
# --------------------------------------------------------------------------- #
class PricingEngine:

    def __init__(self):
        self.base_prices = dict(DEFAULT_BASE_PRICES)

    def _base_price(self, product_type: str):
        return self.base_prices.get(product_type, UNKNOWN_PRODUCT_PRICE)

    @staticmethod
    def _evaluate_discount(discount_logic: str, quantity: int):
        evaluator = SafeExpressionEvaluator({'math': math, 'quantity': quantity})
        return evaluator.evaluate(discount_logic)

    def calculate(self, product_type: str, discount_logic: str, quantity: int):
        try:
            base_price = self._base_price(product_type)
            discount = self._evaluate_discount(discount_logic, quantity)
            return base_price * quantity * (1 - discount)
        except Exception as e:
            raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get('/', response_class=HTMLResponse)
async def calculator_form(request: Request):
    return templates.TemplateResponse(FORM_TEMPLATE_NAME, {'request': request})


@app.post('/calculate')
async def calculate_price(product_type: str=Form(...), discount_logic: str=Form(...), quantity: int=Form(...)):
    engine = PricingEngine()
    try:
        total = engine.calculate(product_type, discount_logic, quantity)
        return {'product': product_type, 'total_price': total}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=HTTP_INTERNAL_ERROR, detail=CALCULATION_ERROR_DETAIL)


# --------------------------------------------------------------------------- #
# CLI helpers
# --------------------------------------------------------------------------- #
def write_form_template():
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    with open(FORM_TEMPLATE_PATH, 'w') as f:
        f.write(FORM_TEMPLATE_HTML)


def main():
    import uvicorn
    write_form_template()
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
