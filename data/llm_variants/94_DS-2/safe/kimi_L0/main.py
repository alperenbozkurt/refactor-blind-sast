"""A small Bottle web app for managing and searching a JSON user store."""

import json
import os

from bottle import Bottle, request, response, template

app = Bottle()
DATA_FILE = 'user_data.json'


def init_data():
    """Create the data file with an empty user list if it does not exist."""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump({'users': []}, f)


def load_data():
    """Load and return the data stored in the JSON data file."""
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    """Write the given data to the JSON data file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


def filter_impl(data, name=None, age=None):
    """Return the items in ``data`` that match the optional name and age."""
    filtered = []
    for item in data:
        name_matches = name is None or name.lower() in item['name'].lower()
        age_matches = age is None or int(item['age']) == int(age)
        if name_matches and age_matches:
            filtered.append(item)
    return filtered


@app.route('/')
def index():
    return """
        <form action="/search" method="post">
            <h2>User Search</h2>
            Name: <input name="name" type="text"><br>
            Age: <input name="age" type="number"><br>
            <button type="submit">Search</button>
        </form>
        <a href="/users">View All Users</a>
    """


@app.route('/users')
def list_users():
    data = load_data()
    return template("""
        <h2>All Users</h2>
        <ul>
            %for user in data['users']:
                <li>{{user['name']}} ({{user['age']}})</li>
            %end
        </ul>
    """, data=data)


@app.post('/search')
def search_users():
    data = load_data()
    name = request.forms.get('name')
    age = request.forms.get('age')
    results = filter_impl(data['users'], name, age)
    return template("""
        <h2>Search Results</h2>
        <ul>
            %for user in results:
                <li>{{user['name']}} ({{user['age']}})</li>
            %end
        </ul>
        <a href="/">New Search</a>
    """, results=results)


@app.post('/add')
def add_user():
    data = load_data()
    name = request.forms.get('name')
    age = int(request.forms.get('age'))
    data['users'].append({'name': name, 'age': age})
    save_data(data)
    return 'User added successfully!'


if __name__ == '__main__':
    init_data()
    app.run(host='localhost', port=8080, debug=True)
