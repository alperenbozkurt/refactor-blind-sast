from bottle import Bottle, request, response, template
import json
import os

app = Bottle()
DATA_FILE = 'user_data.json'

INDEX_HTML = """
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


# --- Data persistence -------------------------------------------------------

def init_data():
    """Create the data file with an empty user list if it does not exist."""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump({'users': []}, f)


def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


# --- Filtering --------------------------------------------------------------

def _name_matches(item, name):
    if name is None:
        return True
    return name.lower() in item['name'].lower()


def _age_matches(item, age):
    if age is None:
        return True
    return int(item['age']) == int(age)


def filter_impl(data, name=None, age=None):
    filtered = []
    for item in data:
        # Both checks are always evaluated (no short-circuit) to preserve
        # the original behaviour, including any exceptions raised.
        name_ok = _name_matches(item, name)
        age_ok = _age_matches(item, age)
        if name_ok and age_ok:
            filtered.append(item)
    return filtered


# --- Routes -----------------------------------------------------------------

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
