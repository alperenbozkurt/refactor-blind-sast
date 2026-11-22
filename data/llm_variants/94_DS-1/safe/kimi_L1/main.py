import csv
import os

from flask import Flask, request, render_template_string

app = Flask(__name__)

INVENTORY_FILE = 'inventory.csv'
CSV_HEADER = ['id', 'name', 'quantity', 'price']

HTML_TEMPLATE = '''
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
'''


def init_inventory():
    """Create the inventory CSV file with a header row if it does not exist."""
    if not os.path.exists(INVENTORY_FILE):
        with open(INVENTORY_FILE, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)


def get_inventory():
    """Return all rows from the inventory CSV file as a list of dicts."""
    with open(INVENTORY_FILE, 'r') as f:
        reader = csv.DictReader(f)
        return list(reader)


def add_item(item_id, name, quantity, price):
    """Validate the fields and append a new item row to the inventory file."""
    if not all([item_id, name, quantity, price]):
        raise ValueError('All fields must be provided')
    with open(INVENTORY_FILE, 'a') as f:
        writer = csv.writer(f)
        writer.writerow([item_id, name, quantity, price])


def search_items(query):
    """Return items whose name contains the query, case-insensitively."""
    return [
        item
        for item in get_inventory()
        if query.lower() in item['name'].lower()
    ]


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        item_id = request.form['id']
        name = request.form['name']
        quantity = request.form['quantity']
        price = request.form['price']
        add_item(item_id, name, quantity, price)
    inventory = get_inventory()
    return render_template_string(HTML_TEMPLATE, inventory=inventory)


@app.route('/search')
def search():
    query = request.args.get('q', '')
    results = search_items(query)
    return render_template_string(HTML_TEMPLATE, inventory=results)


if __name__ == '__main__':
    init_inventory()
    app.run(debug=True)
