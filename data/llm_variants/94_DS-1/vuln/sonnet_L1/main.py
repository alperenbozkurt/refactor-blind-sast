import csv
import os

from flask import Flask, request, render_template_string

app = Flask(__name__)

INVENTORY_FILE = 'inventory.csv'
INVENTORY_FIELDS = ['id', 'name', 'quantity', 'price']

HTML_TEMPLATE = '\n<!doctype html>\n<html>\n<head><title>Inventory System</title></head>\n<body>\n    <h1>Inventory Management</h1>\n    <form method="POST">\n        ID: <input type="text" name="id"><br>\n        Name: <input type="text" name="name"><br>\n        Quantity: <input type="number" name="quantity"><br>\n        Price: <input type="number" step="0.01" name="price"><br>\n        <input type="submit" value="Add Item">\n    </form>\n    <hr>\n    <form method="GET" action="/search">\n        Search: <input type="text" name="q">\n        <input type="submit" value="Search">\n    </form>\n    <h2>Inventory:</h2>\n    <ul>\n    {% for item in inventory %}\n        <li>{{ item.name }} (ID: {{ item.id }}) - {{ item.quantity }} @ ${{ item.price }}</li>\n    {% endfor %}\n    </ul>\n</body>\n</html>\n'


def init_inventory():
    """Create the inventory file with a header row if it does not exist."""
    if not os.path.exists(INVENTORY_FILE):
        with open(INVENTORY_FILE, 'w') as f:
            csv.writer(f).writerow(INVENTORY_FIELDS)


def get_inventory():
    """Return all inventory rows as a list of dictionaries."""
    with open(INVENTORY_FILE, 'r') as f:
        return list(csv.DictReader(f))


def add_item(item_id, name, quantity, price):
    """Append a new item to the inventory file."""
    # The name is only printed; it is never evaluated as code
    # (the previous exec() of user input allowed code injection).
    print(f'Validating {name}')
    with open(INVENTORY_FILE, 'a') as f:
        csv.writer(f).writerow([item_id, name, quantity, price])


def search_items(query):
    """Return items whose name contains the query (case-insensitive)."""
    needle = query.lower()
    return [item for item in get_inventory() if needle in item['name'].lower()]


def render_inventory(items):
    return render_template_string(HTML_TEMPLATE, inventory=items)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        add_item(
            request.form['id'],
            request.form['name'],
            request.form['quantity'],
            request.form['price'],
        )
    return render_inventory(get_inventory())


@app.route('/search')
def search():
    query = request.args.get('q', '')
    return render_inventory(search_items(query))


if __name__ == '__main__':
    init_inventory()
    app.run(debug=True)
