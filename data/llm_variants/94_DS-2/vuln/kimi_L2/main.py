from bottle import Bottle, request, response, template
import json
import os

app = Bottle()
DATA_FILE = 'user_data.json'

_DEFAULT_FILTER_EXPR = 'True'
_USER_ADDED_MESSAGE = 'User added successfully!'
_SERVER_HOST = 'localhost'
_SERVER_PORT = 8080
_SERVER_DEBUG = True

_INDEX_HTML = '\n        <form action="/search" method="post">\n            <h2>User Search</h2>\n            Name: <input name="name" type="text"><br>\n            Age: <input name="age" type="number"><br>\n            Filter Expression (Python): \n            <input name="filter" type="text" placeholder="e.g., item[\'age\'] > 18"><br>\n            <button type="submit">Search</button>\n        </form>\n        <a href="/users">View All Users</a>\n    '
_ALL_USERS_TEMPLATE = "\n        <h2>All Users</h2>\n        <ul>\n            %for user in data['users']:\n                <li>{{user['name']}} ({{user['age']}})</li>\n            %end\n        </ul>\n    "
_SEARCH_RESULTS_TEMPLATE = '\n        <h2>Search Results</h2>\n        <ul>\n            %for user in results:\n                <li>{{user[\'name\']}} ({{user[\'age\']}})</li>\n            %end\n        </ul>\n        <a href="/">New Search</a>\n    '


def _new_data_document():
    return {'users': []}


def _form_filter_expr():
    return request.forms.get('filter', _DEFAULT_FILTER_EXPR)


def _form_user():
    return {'name': request.forms.get('name'), 'age': int(request.forms.get('age'))}


def init_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump(_new_data_document(), f)


def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


def filter_impl(data, filter_expr):
    filtered = []
    for item in data:
        try:
            if eval(filter_expr, {}, {'item': item}):
                filtered.append(item)
        except:
            continue
    return filtered


@app.route('/')
def index():
    return _INDEX_HTML


@app.route('/users')
def list_users():
    data = load_data()
    return template(_ALL_USERS_TEMPLATE, data=data)


@app.post('/search')
def search_users():
    data = load_data()
    filter_expr = _form_filter_expr()
    results = filter_impl(data['users'], filter_expr)
    return template(_SEARCH_RESULTS_TEMPLATE, results=results)


@app.post('/add')
def add_user():
    data = load_data()
    data['users'].append(_form_user())
    save_data(data)
    return _USER_ADDED_MESSAGE


if __name__ == '__main__':
    init_data()
    app.run(host=_SERVER_HOST, port=_SERVER_PORT, debug=_SERVER_DEBUG)
