"""Product catalog web application built on top of Falcon.

The configured WSGI application is exposed as ``app``.  When the module is
executed directly it is served through ``wsgiref``'s development server.
"""

import falcon
import json  # noqa: F401  (unused; preserved as part of the module's public interface)
import html  # noqa: F401  (unused; preserved as part of the module's public interface)
from dataclasses import dataclass
from wsgiref import simple_server

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HTML_CONTENT_TYPE = 'text/html'

ROUTE_PRODUCTS = '/products'
ROUTE_PRODUCT_DETAIL = '/products/{product_id}'
ROUTE_SEARCH = '/search'


@dataclass(frozen=True)
class ServerConfig:
    """Address binding for the bundled development server."""

    host: str = '127.0.0.1'
    port: int = 8000


SERVER_CONFIG = ServerConfig()

# ---------------------------------------------------------------------------
# Catalog data
# ---------------------------------------------------------------------------

DEFAULT_PRODUCTS = [
    {'id': 1, 'name': 'Laptop', 'price': 999.99},
    {'id': 2, 'name': 'Smartphone', 'price': 699.99},
    {'id': 3, 'name': 'Tablet', 'price': 399.99},
    {'id': 4, 'name': 'Headphones', 'price': 149.99},
    {'id': 5, 'name': 'Monitor', 'price': 249.99},
]

# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

PRODUCT_LIST_ITEM_TEMPLATE = (
    '<li>%(name)s - $%(price)s '
    '<a href="/products/%(id)s">View</a></li>'
)

SEARCH_RESULT_ITEM_TEMPLATE = '<li>%(name)s - $%(price)s</li>'

CATALOG_PAGE_TEMPLATE = (
    '\n'
    '            <!DOCTYPE html>\n'
    '            <html>\n'
    '            <head>\n'
    '                <title>Product Catalog</title>\n'
    '                <style>\n'
    '                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }\n'
    '                    .search-box { margin: 20px 0; }\n'
    '                </style>\n'
    '            </head>\n'
    '            <body>\n'
    '                <h1>Product Catalog</h1>\n'
    '                <div class="search-box">\n'
    '                    <form action="/search" method="GET">\n'
    '                        <input type="text" name="query" placeholder="Search products...">\n'
    '                        <button type="submit">Search</button>\n'
    '                    </form>\n'
    '                </div>\n'
    '                <ul>%(products_html)s</ul>\n'
    '            </body>\n'
    '            </html>\n'
    '        '
)

PRODUCT_DETAIL_PAGE_TEMPLATE = (
    '\n'
    '            <!DOCTYPE html>\n'
    '            <html>\n'
    '            <head>\n'
    '                <title>%(name)s</title>\n'
    '            </head>\n'
    '            <body>\n'
    '                <h1>%(name)s</h1>\n'
    '                <p>Price: $%(price)s</p>\n'
    '                <a href="/products">Back to catalog</a>\n'
    '            </body>\n'
    '            </html>\n'
    '        '
)

SEARCH_NO_RESULTS_PAGE_TEMPLATE = (
    '\n'
    '                <!DOCTYPE html>\n'
    '                <html>\n'
    '                <head>\n'
    '                    <title>Search Results</title>\n'
    '                </head>\n'
    '                <body>\n'
    '                    <h1>Search Results</h1>\n'
    '                    <p>No products found for "%(query)s"</p>\n'
    '                    <a href="/products">Back to catalog</a>\n'
    '                </body>\n'
    '                </html>\n'
    '            '
)

SEARCH_RESULTS_PAGE_TEMPLATE = (
    '\n'
    '            <!DOCTYPE html>\n'
    '            <html>\n'
    '            <head>\n'
    '                <title>Search Results</title>\n'
    '            </head>\n'
    '            <body>\n'
    '                <h1>Search Results</h1>\n'
    '                <p>Results for "%(query)s":</p>\n'
    '                <ul>%(results_html)s</ul>\n'
    '                <a href="/products">Back to catalog</a>\n'
    '            </body>\n'
    '            </html>\n'
    '        '
)

# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------


def find_product_by_id(products, product_id):
    """Return the product whose id matches ``product_id``, or ``None``."""
    return next((p for p in products if p['id'] == int(product_id)), None)


def search_products(products, query):
    """Return the products whose name contains ``query`` (case-insensitive)."""
    return [p for p in products if query.lower() in p['name'].lower()]

# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def render_product_list_item(product):
    """Render a single catalog list item."""
    return PRODUCT_LIST_ITEM_TEMPLATE % product


def render_search_result_item(product):
    """Render a single search-result list item."""
    return SEARCH_RESULT_ITEM_TEMPLATE % product


def render_catalog_page(products):
    """Render the full product catalog page."""
    products_html = ''.join(render_product_list_item(p) for p in products)
    return CATALOG_PAGE_TEMPLATE % {'products_html': products_html}


def render_product_detail_page(product):
    """Render the detail page for a single product."""
    return PRODUCT_DETAIL_PAGE_TEMPLATE % product


def render_search_no_results_page(query):
    """Render the search page shown when nothing matches ``query``."""
    return SEARCH_NO_RESULTS_PAGE_TEMPLATE % {'query': query}


def render_search_results_page(query, results):
    """Render the search page listing ``results`` for ``query``."""
    results_html = ''.join(render_search_result_item(p) for p in results)
    return SEARCH_RESULTS_PAGE_TEMPLATE % {'query': query, 'results_html': results_html}

# ---------------------------------------------------------------------------
# HTTP resources
# ---------------------------------------------------------------------------


class ProductResource:
    """Serves the product catalog listing page."""

    products = DEFAULT_PRODUCTS

    def on_get(self, req, resp):
        resp.content_type = HTML_CONTENT_TYPE
        resp.text = render_catalog_page(self.products)


class ProductDetailResource:
    """Serves the detail page for a single product."""

    def on_get(self, req, resp, product_id):
        product = find_product_by_id(ProductResource.products, product_id)
        if not product:
            raise falcon.HTTPNotFound()
        resp.content_type = HTML_CONTENT_TYPE
        resp.text = render_product_detail_page(product)


class SearchResource:
    """Serves product search results."""

    def on_get(self, req, resp):
        query = req.get_param('query', default='')
        results = search_products(ProductResource.products, query)
        resp.content_type = HTML_CONTENT_TYPE
        if not results:
            resp.text = render_search_no_results_page(query)
            return
        resp.text = render_search_results_page(query, results)

# ---------------------------------------------------------------------------
# Application assembly
# ---------------------------------------------------------------------------


def create_app():
    """Create the Falcon application with all routes registered."""
    application = falcon.App()
    application.add_route(ROUTE_PRODUCTS, ProductResource())
    application.add_route(ROUTE_PRODUCT_DETAIL, ProductDetailResource())
    application.add_route(ROUTE_SEARCH, SearchResource())
    return application


app = create_app()


def main():
    """Serve ``app`` with the bundled development WSGI server."""
    httpd = simple_server.make_server(SERVER_CONFIG.host, SERVER_CONFIG.port, app)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
