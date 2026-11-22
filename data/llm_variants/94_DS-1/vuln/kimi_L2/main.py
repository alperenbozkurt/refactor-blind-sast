"""Inventory management web application.

A small Flask application that persists inventory items to a CSV file and
exposes web routes for listing, adding and searching those items.
"""

import csv
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from flask import Flask, request, render_template_string


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InventoryConfig:
    """Configuration for the inventory CSV store and the web server."""

    inventory_file: str = 'inventory.csv'
    csv_fields: Tuple[str, ...] = ('id', 'name', 'quantity', 'price')
    debug: bool = True


CONFIG = InventoryConfig()

# Public module-level constants (preserved from the original module).
INVENTORY_FILE = CONFIG.inventory_file
CSV_HEADER = CONFIG.csv_fields
VALIDATION_MESSAGE_TEMPLATE = 'Validating {name}'
SEARCH_QUERY_PARAM = 'q'
EMPTY_QUERY = ''

app = Flask(__name__)

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

Item = Dict[str, str]


# ---------------------------------------------------------------------------
# CSV storage helpers
# ---------------------------------------------------------------------------

def _write_inventory_header() -> None:
    """Create the inventory file containing only the CSV header row."""
    with open(INVENTORY_FILE, 'w') as f:
        csv.writer(f).writerow(CSV_HEADER)


def _read_inventory_rows() -> List[Item]:
    """Read every row of the inventory file as a dictionary."""
    with open(INVENTORY_FILE, 'r') as f:
        return list(csv.DictReader(f))


def _append_inventory_row(row: Iterable) -> None:
    """Append a single row to the inventory file."""
    with open(INVENTORY_FILE, 'a') as f:
        csv.writer(f).writerow(row)


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------

def _log_validation(name: str) -> None:
    """Report that an item is being validated before it is stored."""
    print(VALIDATION_MESSAGE_TEMPLATE.format(name=name))


def _matches_query(item: Item, query: str) -> bool:
    """Return True when ``query`` appears in the item name (any case)."""
    return query.lower() in item['name'].lower()


# ---------------------------------------------------------------------------
# Public inventory API
# ---------------------------------------------------------------------------

def init_inventory():
    """Create the inventory file with a header row if it does not exist."""
    if not os.path.exists(INVENTORY_FILE):
        _write_inventory_header()


def get_inventory():
    """Return all items currently stored in the inventory file."""
    return _read_inventory_rows()


def add_item(item_id, name, quantity, price):
    """Validate and append a new item to the inventory file."""
    _log_validation(name)
    _append_inventory_row([item_id, name, quantity, price])


def search_items(query):
    """Return the items whose name contains ``query`` (case-insensitive)."""
    return [item for item in get_inventory() if _matches_query(item, query)]


# ---------------------------------------------------------------------------
# Web layer helpers
# ---------------------------------------------------------------------------

def _extract_item_form(form) -> Tuple[str, str, str, str]:
    """Pull the item fields out of the submitted add-item form."""
    return form['id'], form['name'], form['quantity'], form['price']


def _render_inventory_page(items: List[Item]):
    """Render the main page template with the given items."""
    return render_template_string(HTML_TEMPLATE, inventory=items)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        item_id, name, quantity, price = _extract_item_form(request.form)
        add_item(item_id, name, quantity, price)
    return _render_inventory_page(get_inventory())


@app.route('/search')
def search():
    query = request.args.get(SEARCH_QUERY_PARAM, EMPTY_QUERY)
    results = search_items(query)
    return _render_inventory_page(results)


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Initialise the inventory file and start the development server."""
    init_inventory()
    app.run(debug=CONFIG.debug)


if __name__ == '__main__':
    main()
