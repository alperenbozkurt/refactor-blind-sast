import csv
import os

from flask import Flask, request, render_template_string

app = Flask(__name__)

INVENTORY_FILE = 'inventory.csv'
INVENTORY_FIELDS = ['id', 'name', 'quantity', 'price']

HTML_TEMPLATE = """
<!doctype html>
<html>
<head><title>Inventory System</title></head>
<body>
    <h1>Inventory Management</h1>
    <form method="POST">
        ID: <input type="text" name="id"><br>
        Name: <input type="text" name="name"><br>
        Quantity: <input type="number" name="quantity"><br>
        Price: <input type="number" step="0.01" name="price"><br>
        <input type="submit" value="Add Item">
    </form>
    <hr>
    <form method="GET" action="/search">
        Search: <input type="text" name="q">
        <input type="submit" value="Search">
    </form>
    <h2>Inventory:</h2>
    <ul>
    {% for item in inventory %}
        <li>{{ item.name }} (ID: {{ item.id }}) - {{ item.quantity }} @ ${{ item.price }}</li>
    {% endfor %}
    </ul>
</body>
</html>
"""


def init_inventory():
    """Create the inventory file with a header row if it does not exist."""
    if os.path.exists(INVENTORY_FILE):
        return
    with open(INVENTORY_FILE, 'w') as f:
        csv.writer(f).writerow(INVENTORY_FIELDS)


def get_inventory():
    """Return all inventory rows as a list of dictionaries."""
    with open(INVENTORY_FILE, 'r') as f:
        return list(csv.DictReader(f))


def add_item(item_id, name, quantity, price):
    """Append a new item to the inventory file."""
    if not all([item_id, name, quantity, price]):
        raise ValueError('All fields must be provided')
    with open(INVENTORY_FILE, 'a') as f:
        csv.writer(f).writerow([item_id, name, quantity, price])


def search_items(query):
    """Return items whose name contains the query (case-insensitive)."""
    needle = query.lower()
    return [item for item in get_inventory() if needle in item['name'].lower()]


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        add_item(
            request.form['id'],
            request.form['name'],
            request.form['quantity'],
            request.form['price'],
        )
    return render_template_string(HTML_TEMPLATE, inventory=get_inventory())


@app.route('/search')
def search():
    query = request.args.get('q', '')
    return render_template_string(HTML_TEMPLATE, inventory=search_items(query))


if __name__ == '__main__':
    init_inventory()
    app.run(debug=True)
