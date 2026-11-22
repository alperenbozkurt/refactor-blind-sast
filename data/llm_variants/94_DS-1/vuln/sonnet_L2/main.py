import csv
import os

from flask import Flask, request, render_template_string

app = Flask(__name__)

INVENTORY_FILE = 'inventory.csv'

CSV_HEADER = ['id', 'name', 'quantity', 'price']
FORM_FIELDS = ('id', 'name', 'quantity', 'price')
SEARCH_PARAM = 'q'
DEBUG_MODE = True

HTML_TEMPLATE = '\n<!doctype html>\n<html>\n<head><title>Inventory System</title></head>\n<body>\n    <h1>Inventory Management</h1>\n    <form method="POST">\n        ID: <input type="text" name="id"><br>\n        Name: <input type="text" name="name"><br>\n        Quantity: <input type="number" name="quantity"><br>\n        Price: <input type="number" step="0.01" name="price"><br>\n        <input type="submit" value="Add Item">\n    </form>\n    <hr>\n    <form method="GET" action="/search">\n        Search: <input type="text" name="q">\n        <input type="submit" value="Search">\n    </form>\n    <h2>Inventory:</h2>\n    <ul>\n    {% for item in inventory %}\n        <li>{{ item.name }} (ID: {{ item.id }}) - {{ item.quantity }} @ ${{ item.price }}</li>\n    {% endfor %}\n    </ul>\n</body>\n</html>\n'


# --------------------------------------------------------------------------
# Storage helpers
# --------------------------------------------------------------------------

def _write_header():
    with open(INVENTORY_FILE, 'w') as f:
        csv.writer(f).writerow(CSV_HEADER)


def _append_row(row):
    with open(INVENTORY_FILE, 'a') as f:
        csv.writer(f).writerow(row)


def _read_rows():
    with open(INVENTORY_FILE, 'r') as f:
        return list(csv.DictReader(f))


def _announce_validation(name):
    # The original built Python source from user input and exec'd it, which
    # allowed arbitrary code execution. The same message is printed directly.
    print(f'Validating {name}')


def _matches(item, query):
    return query.lower() in item['name'].lower()


# --------------------------------------------------------------------------
# Public inventory API
# --------------------------------------------------------------------------

def init_inventory():
    if not os.path.exists(INVENTORY_FILE):
        _write_header()


def get_inventory():
    return _read_rows()


def add_item(item_id, name, quantity, price):
    _announce_validation(name)
    _append_row([item_id, name, quantity, price])


def search_items(query):
    return [item for item in get_inventory() if _matches(item, query)]


# --------------------------------------------------------------------------
# Web layer
# --------------------------------------------------------------------------

def _render_inventory(items):
    return render_template_string(HTML_TEMPLATE, inventory=items)


def _read_item_form():
    return [request.form[field] for field in FORM_FIELDS]


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        item_id, name, quantity, price = _read_item_form()
        add_item(item_id, name, quantity, price)
    inventory = get_inventory()
    return _render_inventory(inventory)


@app.route('/search')
def search():
    query = request.args.get(SEARCH_PARAM, '')
    results = search_items(query)
    return _render_inventory(results)


def main():
    init_inventory()
    app.run(debug=DEBUG_MODE)


if __name__ == '__main__':
    main()
