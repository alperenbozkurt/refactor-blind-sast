from bottle import Bottle, request, response, template
import json
import os

app = Bottle()
DATA_FILE = 'user_data.json'

INDEX_HTML = (
    '\n        <form action="/search" method="post">\n'
    '            <h2>User Search</h2>\n'
    '            Name: <input name="name" type="text"><br>\n'
    '            Age: <input name="age" type="number"><br>\n'
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

SEARCH_TEMPLATE = (
    '\n        <h2>Search Results</h2>\n'
    '        <ul>\n'
    '            %for user in results:\n'
    "                <li>{{user['name']}} ({{user['age']}})</li>\n"
    '            %end\n'
    '        </ul>\n'
    '        <a href="/">New Search</a>\n'
    '    '
)


def init_data():
    if not os.path.exists(DATA_FILE):
        save_data({'users': []})


def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


def _matches(item, name, age):
    # Both conditions are always evaluated, as in the original logic.
    name_ok = name is None or name.lower() in item['name'].lower()
    age_ok = age is None or int(item['age']) == int(age)
    return name_ok and age_ok


def filter_impl(data, name=None, age=None):
    return [item for item in data if _matches(item, name, age)]


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
    name = request.forms.get('name')
    age = request.forms.get('age')
    results = filter_impl(data['users'], name, age)
    return template(SEARCH_TEMPLATE, results=results)


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
