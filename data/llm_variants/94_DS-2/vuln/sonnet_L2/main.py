import json
import os

from bottle import Bottle, request, response, template

app = Bottle()

# --- Configuration -----------------------------------------------------------

DATA_FILE = 'user_data.json'

SERVER_HOST = 'localhost'
SERVER_PORT = 8080
SERVER_DEBUG = True

DEFAULT_FILTER_EXPR = 'True'
USER_ADDED_MESSAGE = 'User added successfully!'


# --- Templates ---------------------------------------------------------------

INDEX_HTML = (
    '\n        <form action="/search" method="post">\n'
    '            <h2>User Search</h2>\n'
    '            Name: <input name="name" type="text"><br>\n'
    '            Age: <input name="age" type="number"><br>\n'
    '            Filter Expression (Python): \n'
    '            <input name="filter" type="text" placeholder="e.g., item[\'age\'] > 18"><br>\n'
    '            <button type="submit">Search</button>\n'
    '        </form>\n'
    '        <a href="/users">View All Users</a>\n'
    '    '
)

USERS_TEMPLATE = (
    "\n        <h2>All Users</h2>\n"
    "        <ul>\n"
    "            %for user in data['users']:\n"
    "                <li>{{user['name']}} ({{user['age']}})</li>\n"
    "            %end\n"
    "        </ul>\n"
    "    "
)

SEARCH_RESULTS_TEMPLATE = (
    '\n        <h2>Search Results</h2>\n'
    '        <ul>\n'
    '            %for user in results:\n'
    '                <li>{{user[\'name\']}} ({{user[\'age\']}})</li>\n'
    '            %end\n'
    '        </ul>\n'
    '        <a href="/">New Search</a>\n'
    '    '
)


# --- Data persistence --------------------------------------------------------

def _empty_data():
    return {'users': []}


def init_data():
    if not os.path.exists(DATA_FILE):
        save_data(_empty_data())


def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


# --- Filtering ---------------------------------------------------------------

def _matches(item, filter_expr):
    """Evaluate the filter expression against an item.

    NOTE: this uses eval() on user-supplied input, which is inherently unsafe.
    Behaviour is retained as-is; any evaluation error counts as "no match".
    """
    try:
        return bool(eval(filter_expr, {}, {'item': item}))
    except:  # noqa: E722 - preserved: any failure skips the item
        return False


def filter_impl(data, filter_expr):
    return [item for item in data if _matches(item, filter_expr)]


# --- Request helpers ---------------------------------------------------------

def _build_user_from_form():
    return {
        'name': request.forms.get('name'),
        'age': int(request.forms.get('age')),
    }


# --- Routes ------------------------------------------------------------------

@app.route('/')
def index():
    return INDEX_HTML


@app.route('/users')
def list_users():
    data = load_data()
    return template(USERS_TEMPLATE, data=data)


@app.post('/search')
def search_users():
    data = load_data()
    filter_expr = request.forms.get('filter', DEFAULT_FILTER_EXPR)
    results = filter_impl(data['users'], filter_expr)
    return template(SEARCH_RESULTS_TEMPLATE, results=results)


@app.post('/add')
def add_user():
    data = load_data()
    data['users'].append(_build_user_from_form())
    save_data(data)
    return USER_ADDED_MESSAGE


# --- Entry point -------------------------------------------------------------

def main():
    init_data()
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)


if __name__ == '__main__':
    main()
