import json
import os

from bottle import Bottle, request, response, template

app = Bottle()
DATA_FILE = 'user_data.json'

INDEX_HTML = """
        <form action="/search" method="post">
            <h2>User Search</h2>
            Name: <input name="name" type="text"><br>
            Age: <input name="age" type="number"><br>
            Filter Expression (Python): 
            <input name="filter" type="text" placeholder="e.g., item['age'] > 18"><br>
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

SEARCH_TEMPLATE = """
        <h2>Search Results</h2>
        <ul>
            %for user in results:
                <li>{{user['name']}} ({{user['age']}})</li>
            %end
        </ul>
        <a href="/">New Search</a>
    """


def init_data():
    if not os.path.exists(DATA_FILE):
        save_data({'users': []})


def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


def _matches(item, filter_expr):
    try:
        return bool(eval(filter_expr, {}, {'item': item}))
    except Exception:
        return False


def filter_impl(data, filter_expr):
    return [item for item in data if _matches(item, filter_expr)]


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
    filter_expr = request.forms.get('filter', 'True')
    results = filter_impl(data['users'], filter_expr)
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
