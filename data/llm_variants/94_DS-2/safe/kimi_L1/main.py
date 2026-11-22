"""Simple Bottle web app for searching and storing users."""

import json
import os

from bottle import Bottle, request, response, template

app = Bottle()
DATA_FILE = 'user_data.json'


def init_data():
    """Create the data file with an empty user list if it is missing."""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump({'users': []}, f)


def load_data():
    """Read and return the user data from the data file."""
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    """Write the given user data to the data file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


def filter_impl(data, name=None, age=None):
    """Return the entries in ``data`` matching the given name and/or age.

    A ``None`` criterion matches everything. The name criterion matches
    case-insensitive substrings; the age criterion matches exact ages.
    """
    filtered = []
    for item in data:
        name_matches = name is None or name.lower() in item['name'].lower()
        age_matches = age is None or int(item['age']) == int(age)
        if name_matches and age_matches:
            filtered.append(item)
    return filtered


@app.route('/')
def index():
    """Render the search form."""
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
    """Render the list of all users."""
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
    """Render the users matching the submitted name and/or age."""
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
    """Add the submitted user to the data file."""
    data = load_data()
    user = {
        'name': request.forms.get('name'),
        'age': int(request.forms.get('age')),
    }
    data['users'].append(user)
    save_data(data)
    return 'User added successfully!'


if __name__ == '__main__':
    init_data()
    app.run(host='localhost', port=8080, debug=True)
