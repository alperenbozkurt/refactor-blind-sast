"""User directory web application backed by a JSON file."""

import json
import os
from dataclasses import dataclass

from bottle import Bottle, request, response, template

app = Bottle()

DATA_FILE = 'user_data.json'

INDEX_TEMPLATE = """
        <form action="/search" method="post">
            <h2>User Search</h2>
            Name: <input name="name" type="text"><br>
            Age: <input name="age" type="number"><br>
            <button type="submit">Search</button>
        </form>
        <a href="/users">View All Users</a>
    """

USERS_TEMPLATE = """
        <h2>All Users</h2>
        <ul>
            %for user in data['users']:
                <li>{{user['name']}} ({{user['age']}})</li>
            %end
        </ul>
    """

SEARCH_RESULTS_TEMPLATE = """
        <h2>Search Results</h2>
        <ul>
            %for user in results:
                <li>{{user['name']}} ({{user['age']}})</li>
            %end
        </ul>
        <a href="/">New Search</a>
    """

ADD_USER_SUCCESS_MESSAGE = 'User added successfully!'


@dataclass(frozen=True)
class ServerConfig:
    """Settings used when running the development server."""

    host: str = 'localhost'
    port: int = 8080
    debug: bool = True


SERVER_CONFIG = ServerConfig()


class JsonDataStore:
    """JSON-file-backed storage for the application data."""

    def __init__(self, path):
        self.path = path

    @staticmethod
    def default_data():
        return {'users': []}

    def init(self):
        if not os.path.exists(self.path):
            self.save(self.default_data())

    def load(self):
        with open(self.path) as f:
            return json.load(f)

    def save(self, data):
        with open(self.path, 'w') as f:
            json.dump(data, f)


def _get_store():
    return JsonDataStore(DATA_FILE)


def init_data():
    """Create the data file with an empty user list if it does not exist."""
    _get_store().init()


def load_data():
    """Load and return the persisted application data."""
    return _get_store().load()


def save_data(data):
    """Persist the application data."""
    _get_store().save(data)


def _user_matches(item, name, age):
    name_matches = name is None or name.lower() in item['name'].lower()
    age_matches = age is None or int(item['age']) == int(age)
    return name_matches and age_matches


def filter_impl(data, name=None, age=None):
    """Return the users matching the optional name/age filters."""
    filtered = []
    for item in data:
        if _user_matches(item, name, age):
            filtered.append(item)
    return filtered


def _build_user(form):
    return {'name': form.get('name'), 'age': int(form.get('age'))}


@app.route('/')
def index():
    return INDEX_TEMPLATE


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
    return template(SEARCH_RESULTS_TEMPLATE, results=results)


@app.post('/add')
def add_user():
    data = load_data()
    data['users'].append(_build_user(request.forms))
    save_data(data)
    return ADD_USER_SUCCESS_MESSAGE


if __name__ == '__main__':
    init_data()
    app.run(host=SERVER_CONFIG.host, port=SERVER_CONFIG.port, debug=SERVER_CONFIG.debug)
