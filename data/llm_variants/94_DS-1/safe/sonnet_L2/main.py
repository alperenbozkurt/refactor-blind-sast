import csv
import os

from flask import Flask, request, render_template_string

app = Flask(__name__)

# --------------------------------------------------------------------------
# Configuration constants
# --------------------------------------------------------------------------
INVENTORY_FILE = 'inventory.csv'

CSV_HEADER = ['id', 'name', 'quantity', 'price']

MODE_READ = 'r'
MODE_WRITE = 'w'
MODE_APPEND = 'a'

ERROR_MISSING_FIELDS = 'All fields must be provided'

FORM_FIELD_ID = 'id'
FORM_FIELD_NAME = 'name'
FORM_FIELD_QUANTITY = 'quantity'
FORM_FIELD_PRICE = 'price'
SEARCH_QUERY_PARAM = 'q'

HTML_TEMPLATE = '\n<!doctype html>\n<html>\n<head><title>Inventory System</title></head>\n<body>\n    <h1>Inventory Management</h1>\n    <form method="POST">\n        ID: <input type="text" name="id"><br>\n        Name: <input type="text" name="name"><br>\n        Quantity: <input type="number" name="quantity"><br>\n        Price: <input type="number" step="0.01" name="price"><br>\n        <input type="submit" value="Add Item">\n    </form>\n    <hr>\n    <form method="GET" action="/search">\n        Search: <input type="text" name="q">\n        <input type="submit" value="Search">\n    </form>\n    <h2>Inventory:</h2>\n    <ul>\n    {% for item in inventory %}\n        <li>{{ item.name }} (ID: {{ item.id }}) - {{ item.quantity }} @ ${{ item.price }}</li>\n    {% endfor %}\n    </ul>\n</body>\n</html>\n'


# --------------------------------------------------------------------------
# Storage helpers (INVENTORY_FILE is looked up at call time on purpose)
# --------------------------------------------------------------------------
def _write_header():
    with open(INVENTORY_FILE, MODE_WRITE) as f:
        csv.writer(f).writerow(CSV_HEADER)


def _append_row(row):
    with open(INVENTORY_FILE, MODE_APPEND) as f:
        csv.writer(f).writerow(row)


def _read_rows():
    with open(INVENTORY_FILE, MODE_READ) as f:
        return list(csv.DictReader(f))


def _validate_fields(*fields):
    if not all(list(fields)):
        raise ValueError(ERROR_MISSING_FIELDS)


def _name_matches(item, query):
    return query.lower() in item[FORM_FIELD_NAME].lower()


# --------------------------------------------------------------------------
# Public inventory API
# --------------------------------------------------------------------------
def init_inventory():
    if not os.path.exists(INVENTORY_FILE):
        _write_header()


def get_inventory():
    return _read_rows()


def add_item(item_id, name, quantity, price):
    _validate_fields(item_id, name, quantity, price)
    _append_row([item_id, name, quantity, price])


def search_items(query):
    return [item for item in get_inventory() if _name_matches(item, query)]


# --------------------------------------------------------------------------
# Web layer helpers
# --------------------------------------------------------------------------
def _render_inventory(inventory):
    return render_template_string(HTML_TEMPLATE, inventory=inventory)


def _add_item_from_form():
    item_id = request.form[FORM_FIELD_ID]
    name = request.form[FORM_FIELD_NAME]
    quantity = request.form[FORM_FIELD_QUANTITY]
    price = request.form[FORM_FIELD_PRICE]
    add_item(item_id, name, quantity, price)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        _add_item_from_form()
    inventory = get_inventory()
    return _render_inventory(inventory)


@app.route('/search')
def search():
    query = request.args.get(SEARCH_QUERY_PARAM, '')
    results = search_items(query)
    return _render_inventory(results)


if __name__ == '__main__':
    init_inventory()
    app.run(debug=True)
