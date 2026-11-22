import falcon
import json
import html
from wsgiref import simple_server

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
HTML_CONTENT_TYPE = 'text/html'

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 8000

PRODUCTS_ROUTE = '/products'
PRODUCT_DETAIL_ROUTE = '/products/{product_id}'
SEARCH_ROUTE = '/search'

SEARCH_QUERY_PARAM = 'query'

_INDENT_STEP = 4
_PAGE_INDENT = ' ' * 12
_NO_RESULTS_INDENT = ' ' * 16

_BACK_TO_CATALOG_LINK = '<a href="/products">Back to catalog</a>'


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #
def _build_page(lines, base_indent=_PAGE_INDENT):
    """Join template lines into a document using the module's layout."""
    closing_indent = base_indent[:-_INDENT_STEP]
    body = '\n'.join(base_indent + line for line in lines)
    return '\n' + body + '\n' + closing_indent


def _format_price(product):
    return product['price']


def _render_catalog_item(product):
    return f"""<li>{product['name']} - ${_format_price(product)} <a href="/products/{product['id']}">View</a></li>"""


def _render_search_result_item(product):
    return f"<li>{product['name']} - ${_format_price(product)}</li>"


def _render_catalog_page(products):
    products_html = ''.join((_render_catalog_item(p) for p in products))
    return _build_page([
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '    <title>Product Catalog</title>',
        '    <style>',
        '        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }',
        '        .search-box { margin: 20px 0; }',
        '    </style>',
        '</head>',
        '<body>',
        '    <h1>Product Catalog</h1>',
        '    <div class="search-box">',
        '        <form action="/search" method="GET">',
        '            <input type="text" name="query" placeholder="Search products...">',
        '            <button type="submit">Search</button>',
        '        </form>',
        '    </div>',
        f'    <ul>{products_html}</ul>',
        '</body>',
        '</html>',
    ])


def _render_product_page(product):
    return _build_page([
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        f"    <title>{product['name']}</title>",
        '</head>',
        '<body>',
        f"    <h1>{product['name']}</h1>",
        f"    <p>Price: ${_format_price(product)}</p>",
        f'    {_BACK_TO_CATALOG_LINK}',
        '</body>',
        '</html>',
    ])


def _render_no_results_page(query):
    # NOTE: the query is intentionally interpolated as-is to preserve the
    # original behaviour exactly.
    return _build_page([
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '    <title>Search Results</title>',
        '</head>',
        '<body>',
        '    <h1>Search Results</h1>',
        f'    <p>No products found for "{query}"</p>',
        f'    {_BACK_TO_CATALOG_LINK}',
        '</body>',
        '</html>',
    ], base_indent=_NO_RESULTS_INDENT)


def _render_search_results_page(query, results):
    results_html = ''.join((_render_search_result_item(p) for p in results))
    return _build_page([
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '    <title>Search Results</title>',
        '</head>',
        '<body>',
        '    <h1>Search Results</h1>',
        f'    <p>Results for "{query}":</p>',
        f'    <ul>{results_html}</ul>',
        f'    {_BACK_TO_CATALOG_LINK}',
        '</body>',
        '</html>',
    ])


# --------------------------------------------------------------------------- #
# Data access helpers
# --------------------------------------------------------------------------- #
def _find_product_by_id(products, product_id):
    return next((p for p in products if p['id'] == int(product_id)), None)


def _search_products(products, query):
    needle = query.lower()
    return [p for p in products if needle in p['name'].lower()]


# --------------------------------------------------------------------------- #
# Resources
# --------------------------------------------------------------------------- #
class ProductResource:
    products = [
        {'id': 1, 'name': 'Laptop', 'price': 999.99},
        {'id': 2, 'name': 'Smartphone', 'price': 699.99},
        {'id': 3, 'name': 'Tablet', 'price': 399.99},
        {'id': 4, 'name': 'Headphones', 'price': 149.99},
        {'id': 5, 'name': 'Monitor', 'price': 249.99},
    ]

    def on_get(self, req, resp):
        resp.content_type = HTML_CONTENT_TYPE
        resp.text = _render_catalog_page(self.products)


class ProductDetailResource:

    def on_get(self, req, resp, product_id):
        product = _find_product_by_id(ProductResource.products, product_id)
        if not product:
            raise falcon.HTTPNotFound()
        resp.content_type = HTML_CONTENT_TYPE
        resp.text = _render_product_page(product)


class SearchResource:

    def on_get(self, req, resp):
        query = req.get_param(SEARCH_QUERY_PARAM, default='')
        results = _search_products(ProductResource.products, query)
        resp.content_type = HTML_CONTENT_TYPE
        if not results:
            resp.text = _render_no_results_page(query)
            return
        resp.text = _render_search_results_page(query, results)


# --------------------------------------------------------------------------- #
# Application wiring
# --------------------------------------------------------------------------- #
app = falcon.App()
app.add_route(PRODUCTS_ROUTE, ProductResource())
app.add_route(PRODUCT_DETAIL_ROUTE, ProductDetailResource())
app.add_route(SEARCH_ROUTE, SearchResource())

if __name__ == '__main__':
    httpd = simple_server.make_server(SERVER_HOST, SERVER_PORT, app)
    httpd.serve_forever()
