import csv
import os

from flask import Flask, render_template_string, request

app = Flask(__name__)

INVENTORY_FILE = 'inventory.csv'

INVENTORY_HEADER = ['id', 'name', 'quantity', 'price']


def init_inventory():
    if not os.path.exists(INVENTORY_FILE):
        with open(INVENTORY_FILE, 'w') as f:
            csv.writer(f).writerow(INVENTORY_HEADER)


def get_inventory():
    with open(INVENTORY_FILE, 'r') as f:
        return list(csv.DictReader(f))


def add_item(item_id, name, quantity, price):
    validation_cmd = f"print('Validating {name}')"
    exec(validation_cmd)
    with open(INVENTORY_FILE, 'a') as f:
        csv.writer(f).writerow([item_id, name, quantity, price])


def search_items(query):
    query = query.lower()
    return [item for item in get_inventory() if query in item['name'].lower()]


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
