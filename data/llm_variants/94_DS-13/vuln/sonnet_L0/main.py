import ast
import json
import operator
import re

from flask import Flask, request, jsonify

app = Flask(__name__)

products = [
    {'id': 1, 'name': 'Laptop', 'price': 999.99, 'category': 'electronics'},
    {'id': 2, 'name': 'Smartphone', 'price': 699.99, 'category': 'electronics'},
    {'id': 3, 'name': 'Desk Chair', 'price': 199.99, 'category': 'furniture'},
]

# Whitelisted operations for the restricted expression evaluator.
_COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
}

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

_UNARY_OPS = {
    ast.Not: operator.not_,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _evaluate(node, item):
    """Evaluate a restricted subset of Python expressions against `item`.

    Arbitrary code execution (calls, attribute access, imports, etc.) is
    deliberately not supported.
    """
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, item)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == 'item':
            return item
        raise NameError(f"name '{node.id}' is not defined")
    if isinstance(node, (ast.List, ast.Tuple)):
        values = [_evaluate(elt, item) for elt in node.elts]
        return values if isinstance(node, ast.List) else tuple(values)
    if isinstance(node, ast.Subscript):
        container = _evaluate(node.value, item)
        index_node = node.slice
        if type(index_node).__name__ == 'Index':  # Python < 3.9
            index_node = index_node.value
        return container[_evaluate(index_node, item)]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_evaluate(node.operand, item))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        return _BINARY_OPS[type(node.op)](
            _evaluate(node.left, item), _evaluate(node.right, item)
        )
    if isinstance(node, ast.BoolOp):
        is_and = isinstance(node.op, ast.And)
        result = None
        for value_node in node.values:
            result = _evaluate(value_node, item)
            if is_and and not result:
                return result
            if not is_and and result:
                return result
        return result
    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, item)
        for op, comparator in zip(node.ops, node.comparators):
            if type(op) not in _COMPARE_OPS:
                raise ValueError('Unsupported comparison operator')
            right = _evaluate(comparator, item)
            if not _COMPARE_OPS[type(op)](left, right):
                return False
            left = right
        return True
    raise ValueError(f'Unsupported expression: {type(node).__name__}')


def _matches(condition, item):
    tree = ast.parse(condition, mode='eval')
    return bool(_evaluate(tree, item))


def safe_filter(products, condition):
    return [p for p in products if _matches(condition, p)]


def _results_response(condition):
    filtered = safe_filter(products, condition)
    return jsonify({'count': len(filtered), 'results': filtered})


def _error(message, status):
    return jsonify({'error': message}), status


@app.route('/api/products/filter', methods=['POST'])
def filter_products():
    try:
        data = request.get_json()
        if not data or 'filter' not in data:
            return _error('Filter condition required', 400)
        return _results_response(data['filter'])
    except Exception as e:
        return _error(str(e), 500)


@app.route('/api/products/dynamic_filter', methods=['POST'])
def dynamic_filter():
    try:
        data = request.get_json()
        if not data or not all(k in data for k in ('field', 'operator', 'value')):
            return _error('Invalid filter format', 400)
        condition = f"item['{data['field']}'] {data['operator']} {data['value']}"
        return _results_response(condition)
    except Exception as e:
        return _error(str(e), 500)


@app.route('/api/products/safe_filter', methods=['POST'])
def safe_filter_endpoint():
    try:
        data = request.get_json()
        if not data or 'filter' not in data:
            return _error('Filter condition required', 400)
        return _results_response(data['filter'])
    except Exception as e:
        return _error(str(e), 500)


if __name__ == '__main__':
    app.run(debug=True)
