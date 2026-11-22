"""Simple user-search web application built with Bottle."""

import json
import os

from bottle import Bottle, request, response, template

app = Bottle()

DATA_FILE = 'user_data.json'

INDEX_PAGE = (
    '\n'
    '        <form action="/search" method="post">\n'
    '            <h2>User Search</h2>\n'
    '            Name: <input name="name" type="text"><br>\n'
    '            Age: <input name="age" type="number"><br>\n'
    '            Filter Expression (Python): \n'
    '            <input name="filter" type="text" '
    'placeholder="e.g., item[\'age\'] > 18"><br>\n'
    '            <button type="submit">Search</button>\n'
    '        </form>\n'
    '        <a href="/users">View All Users</a>\n'
    '    '
)

USERS_TEMPLATE = (
    '\n'
    '        <h2>All Users</h2>\n'
    '        <ul>\n'
    "            %for user in data['users']:\n"
    "                <li>{{user['name']}} ({{user['age']}})</li>\n"
    '            %end\n'
    '        </ul>\n'
    '    '
)

SEARCH_RESULTS_TEMPLATE = (
    '\n'
    '        <h2>Search Results</h2>\n'
    '        <ul>\n'
    '            %for user in results:\n'
    "                <li>{{user['name']}} ({{user['age']}})</li>\n"
    '            %end\n'
    '        </ul>\n'
    '        <a href="/">New Search</a>\n'
    '    '
)


def init_data():
    """Create the JSON data file with an empty user list if it is missing."""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump({'users': []}, f)


def load_data():
    """Read and return the persisted data."""
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    """Persist ``data`` to the JSON data file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


def filter_impl(data, filter_expr):
    """Return the items of ``data`` for which ``filter_expr`` is truthy.

    The expression is evaluated with the current entry bound to ``item``;
    entries that raise any error during evaluation are skipped.
    """
    filtered = []
    for item in data:
        try:
            if eval(filter_expr, {}, {'item': item}):
                filtered.append(item)
        except BaseException:
            continue
    return filtered


@app.route('/')
def index():
    return INDEX_PAGE


@app.route('/users')
def list_users():
    data = load_data()
    return template(USERS_TEMPLATE, data=data)


@app.post('/search')
def search_users():
    data = load_data()
    filter_expr = request.forms.get('filter', 'True')
    results = filter_impl(data['users'], filter_expr)
    return template(SEARCH_RESULTS_TEMPLATE, results=results)


@app.post('/add')
def add_user():
    data = load_data()
    data['users'].append({
        'name': request.forms.get('name'),
        'age': int(request.forms.get('age')),
    })
    save_data(data)
    return 'User added successfully!'


if __name__ == '__main__':
    init_data()
    app.run(host='localhost', port=8080, debug=True)
