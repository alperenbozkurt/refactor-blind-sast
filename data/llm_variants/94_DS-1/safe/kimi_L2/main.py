"""CSV-backed inventory management web application.

A small Flask app for adding and searching inventory items persisted in a
CSV file. Storage, validation and rendering are split into small helpers so
the module stays easy to extend and test as the codebase grows.
"""

import csv
import os
from dataclasses import dataclass

from flask import Flask, request, render_template_string

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

INVENTORY_FILE = 'inventory.csv'

FIELD_ID = 'id'
FIELD_NAME = 'name'
FIELD_QUANTITY = 'quantity'
FIELD_PRICE = 'price'
INVENTORY_FIELDS = (FIELD_ID, FIELD_NAME, FIELD_QUANTITY, FIELD_PRICE)
CSV_HEADER = list(INVENTORY_FIELDS)

ERROR_MISSING_FIELDS = 'All fields must be provided'

INDEX_ROUTE = '/'
SEARCH_ROUTE = '/search'
SEARCH_QUERY_PARAM = 'q'
DEFAULT_SEARCH_QUERY = ''

HTTP_GET = 'GET'
HTTP_POST = 'POST'

DEBUG_MODE = True


@dataclass(frozen=True)
class InventoryConfig:
    """Static configuration for the inventory store."""

    fields: tuple = INVENTORY_FIELDS
    missing_fields_error: str = ERROR_MISSING_FIELDS


CONFIG = InventoryConfig()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _write_rows(file_path, rows, mode):
    """Write ``rows`` to the CSV file at ``file_path`` using ``mode``."""
    with open(file_path, mode) as csv_file:
        writer = csv.writer(csv_file)
        writer.writerows(rows)


def _read_items(file_path):
    """Return every row of the CSV file at ``file_path`` as a dictionary."""
    with open(file_path, 'r') as csv_file:
        return list(csv.DictReader(csv_file))


def _validate_required_fields(values):
    """Raise ``ValueError`` unless every value in ``values`` is provided."""
    if not all(values):
        raise ValueError(CONFIG.missing_fields_error)


def _matches_query(item, query):
    """Return True if ``query`` is a case-insensitive substring of the name."""
    return query.lower() in item[FIELD_NAME].lower()


def _extract_item_data(form):
    """Pull the item fields out of ``form`` in ``add_item`` argument order."""
    return [form[field] for field in CONFIG.fields]


def _render_inventory_page(inventory):
    """Render the inventory page template with the given items."""
    return render_template_string(HTML_TEMPLATE, inventory=inventory)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_inventory():
    """Create the inventory CSV file with its header row if it is missing."""
    if not os.path.exists(INVENTORY_FILE):
        _write_rows(INVENTORY_FILE, [CSV_HEADER], 'w')


def get_inventory():
    """Return the full inventory as a list of row dictionaries."""
    return _read_items(INVENTORY_FILE)


def add_item(item_id, name, quantity, price):
    """Validate and append a single item to the inventory CSV file."""
    _validate_required_fields([item_id, name, quantity, price])
    _write_rows(INVENTORY_FILE, [[item_id, name, quantity, price]], 'a')


def search_items(query):
    """Return all items whose name contains ``query`` (case-insensitive)."""
    return [item for item in get_inventory() if _matches_query(item, query)]


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route(INDEX_ROUTE, methods=[HTTP_GET, HTTP_POST])
def index():
    if request.method == HTTP_POST:
        add_item(*_extract_item_data(request.form))
    inventory = get_inventory()
    return _render_inventory_page(inventory)


@app.route(SEARCH_ROUTE)
def search():
    query = request.args.get(SEARCH_QUERY_PARAM, DEFAULT_SEARCH_QUERY)
    results = search_items(query)
    return _render_inventory_page(results)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    init_inventory()
    app.run(debug=DEBUG_MODE)


if __name__ == '__main__':
    main()
