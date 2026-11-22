from bottle import Bottle, request, response, template
import json
import os

app = Bottle()

# --------------------------------------------------------------------------
# Configuration constants
# --------------------------------------------------------------------------
DATA_FILE = 'user_data.json'

SERVER_HOST = 'localhost'
SERVER_PORT = 8080
SERVER_DEBUG = True

USERS_KEY = 'users'
NAME_FIELD = 'name'
AGE_FIELD = 'age'

USER_ADDED_MESSAGE = 'User added successfully!'

# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------
INDEX_HTML = '\n        <form action="/search" method="post">\n            <h2>User Search</h2>\n            Name: <input name="name" type="text"><br>\n            Age: <input name="age" type="number"><br>\n            <button type="submit">Search</button>\n        </form>\n        <a href="/users">View All Users</a>\n    '

USER_LIST_TEMPLATE = "\n        <h2>All Users</h2>\n        <ul>\n            %for user in data['users']:\n                <li>{{user['name']}} ({{user['age']}})</li>\n            %end\n        </ul>\n    "

SEARCH_RESULTS_TEMPLATE = '\n        <h2>Search Results</h2>\n        <ul>\n            %for user in results:\n                <li>{{user[\'name\']}} ({{user[\'age\']}})</li>\n            %end\n        </ul>\n        <a href="/">New Search</a>\n    '


# --------------------------------------------------------------------------
# Persistence helpers
# --------------------------------------------------------------------------
def init_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump({USERS_KEY: []}, f)


def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


# --------------------------------------------------------------------------
# Filtering helpers
# --------------------------------------------------------------------------
def _name_matches(item, name):
    if name is None:
        return True
    return name.lower() in item[NAME_FIELD].lower()


def _age_matches(item, age):
    if age is None:
        return True
    return int(item[AGE_FIELD]) == int(age)


def filter_impl(data, name=None, age=None):
    filtered = []
    for item in data:
        # Both checks are always evaluated (no short-circuit), as before.
        name_ok = _name_matches(item, name)
        age_ok = _age_matches(item, age)
        if name_ok and age_ok:
            filtered.append(item)
    return filtered


# --------------------------------------------------------------------------
# Request helpers
# --------------------------------------------------------------------------
def _build_user_from_form():
    return {
        NAME_FIELD: request.forms.get(NAME_FIELD),
        AGE_FIELD: int(request.forms.get(AGE_FIELD)),
    }


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route('/')
def index():
    return INDEX_HTML


@app.route('/users')
def list_users():
    data = load_data()
    return template(USER_LIST_TEMPLATE, data=data)


@app.post('/search')
def search_users():
    data = load_data()
    name = request.forms.get(NAME_FIELD)
    age = request.forms.get(AGE_FIELD)
    results = filter_impl(data[USERS_KEY], name, age)
    return template(SEARCH_RESULTS_TEMPLATE, results=results)


@app.post('/add')
def add_user():
    data = load_data()
    data[USERS_KEY].append(_build_user_from_form())
    save_data(data)
    return USER_ADDED_MESSAGE


if __name__ == '__main__':
    init_data()
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
