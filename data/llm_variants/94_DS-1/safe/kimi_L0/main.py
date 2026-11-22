import csv
import os

from flask import Flask, render_template_string, request

app = Flask(__name__)

INVENTORY_FILE = 'inventory.csv'

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
    """Create the inventory CSV file with a header row if it does not exist."""
    if not os.path.exists(INVENTORY_FILE):
        with open(INVENTORY_FILE, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'name', 'quantity', 'price'])


def get_inventory():
    """Return all inventory items as a list of dictionaries."""
    with open(INVENTORY_FILE, 'r') as f:
        return list(csv.DictReader(f))


def add_item(item_id, name, quantity, price):
    """Append a new item row to the inventory CSV file."""
    if not all([item_id, name, quantity, price]):
        raise ValueError('All fields must be provided')
    with open(INVENTORY_FILE, 'a') as f:
        writer = csv.writer(f)
        writer.writerow([item_id, name, quantity, price])


def search_items(query):
    """Return all items whose name contains the query (case-insensitive)."""
    query = query.lower()
    return [item for item in get_inventory() if query in item['name'].lower()]


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
