"""Product catalog web application built with Falcon.

Serves a small HTML product catalog along with product detail pages and
a simple search endpoint. Running the module directly starts a
development server at http://127.0.0.1:8000.
"""

import html
from wsgiref import simple_server

import falcon

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONTENT_TYPE_HTML = 'text/html'

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 8000

ROUTE_PRODUCTS = '/products'
ROUTE_PRODUCT_DETAIL = '/products/{product_id}'
ROUTE_SEARCH = '/search'

SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Content-Security-Policy': "default-src 'self'",
}

PRODUCTS = [
    {'id': 1, 'name': 'Laptop', 'price': 999.99},
    {'id': 2, 'name': 'Smartphone', 'price': 699.99},
    {'id': 3, 'name': 'Tablet', 'price': 399.99},
    {'id': 4, 'name': 'Headphones', 'price': 149.99},
    {'id': 5, 'name': 'Monitor', 'price': 249.99},
]


# ---------------------------------------------------------------------------
# HTML rendering helpers
# ---------------------------------------------------------------------------

def _render_catalog_item(product):
    """Render a product as a catalog list item with a detail-page link."""
    return f"""<li>{html.escape(product['name'])} - ${html.escape(str(product['price']))} <a href="/products/{html.escape(str(product['id']))}">View</a></li>"""


def _render_search_result_item(product):
    """Render a product as a search-result list item."""
    return f"<li>{html.escape(product['name'])} - ${html.escape(str(product['price']))}</li>"


def _render_catalog_page(products_html):
    """Render the full product catalog page."""
    return (
        '\n            <!DOCTYPE html>'
        '\n            <html>'
        '\n            <head>'
        '\n                <title>Product Catalog</title>'
        '\n                <meta name="viewport" content="width=device-width, initial-scale=1">'
        '\n                <style>'
        '\n                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }'
        '\n                    .search-box { margin: 20px 0; }'
        '\n                </style>'
        '\n            </head>'
        '\n            <body>'
        '\n                <h1>Product Catalog</h1>'
        '\n                <div class="search-box">'
        '\n                    <form action="/search" method="GET">'
        '\n                        <input type="text" name="query" placeholder="Search products..." required>'
        '\n                        <button type="submit">Search</button>'
        '\n                    </form>'
        '\n                </div>'
        f'\n                <ul>{products_html}</ul>'
        '\n            </body>'
        '\n            </html>'
        '\n        '
    )


def _render_product_detail_page(product):
    """Render the detail page for a single product."""
    safe_name = html.escape(product['name'])
    safe_price = html.escape(str(product['price']))
    return (
        '\n            <!DOCTYPE html>'
        '\n            <html>'
        '\n            <head>'
        f'\n                <title>{safe_name}</title>'
        '\n                <meta name="viewport" content="width=device-width, initial-scale=1">'
        '\n            </head>'
        '\n            <body>'
        f'\n                <h1>{safe_name}</h1>'
        f'\n                <p>Price: ${safe_price}</p>'
        '\n                <a href="/products">Back to catalog</a>'
        '\n            </body>'
        '\n            </html>'
        '\n        '
    )


def _render_no_results_page(safe_query):
    """Render the search page shown when no products match the query."""
    return (
        '\n                <!DOCTYPE html>'
        '\n                <html>'
        '\n                <head>'
        '\n                    <title>Search Results</title>'
        '\n                    <meta name="viewport" content="width=device-width, initial-scale=1">'
        '\n                </head>'
        '\n                <body>'
        '\n                    <h1>Search Results</h1>'
        f'\n                    <p>No products found for "{safe_query}"</p>'
        '\n                    <a href="/products">Back to catalog</a>'
        '\n                </body>'
        '\n                </html>'
        '\n            '
    )


def _render_search_results_page(safe_query, results_html):
    """Render the search page listing the matching products."""
    return (
        '\n            <!DOCTYPE html>'
        '\n            <html>'
        '\n            <head>'
        '\n                <title>Search Results</title>'
        '\n                <meta name="viewport" content="width=device-width, initial-scale=1">'
        '\n            </head>'
        '\n            <body>'
        '\n                <h1>Search Results</h1>'
        f'\n                <p>Results for "{safe_query}":</p>'
        f'\n                <ul>{results_html}</ul>'
        '\n                <a href="/products">Back to catalog</a>'
        '\n            </body>'
        '\n            </html>'
        '\n        '
    )


# ---------------------------------------------------------------------------
# Product data helpers
# ---------------------------------------------------------------------------

def _find_product(products, product_id):
    """Return the product with the given ID, or None if there is no match."""
    return next((p for p in products if p['id'] == product_id), None)


def _search_products(products, query):
    """Return products whose name contains the query (case-insensitive)."""
    query_lower = query.lower()
    return [p for p in products if query_lower in p['name'].lower()]


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

class ProductResource:
    """Serves the product catalog listing page."""

    products = PRODUCTS

    def on_get(self, req, resp):
        resp.content_type = CONTENT_TYPE_HTML
        products_html = ''.join(_render_catalog_item(p) for p in self.products)
        resp.text = _render_catalog_page(products_html)


class ProductDetailResource:
    """Serves the detail page for a single product."""

    def on_get(self, req, resp, product_id):
        try:
            product_id = int(product_id)
        except ValueError:
            raise falcon.HTTPBadRequest('Invalid product ID')
        product = _find_product(ProductResource.products, product_id)
        if not product:
            raise falcon.HTTPNotFound()
        resp.content_type = CONTENT_TYPE_HTML
        resp.text = _render_product_detail_page(product)


class SearchResource:
    """Serves product search results."""

    def on_get(self, req, resp):
        query = req.get_param('query', default='')
        safe_query = html.escape(query)
        results = _search_products(ProductResource.products, query)
        resp.content_type = CONTENT_TYPE_HTML
        if not results:
            resp.text = _render_no_results_page(safe_query)
            return
        results_html = ''.join(_render_search_result_item(p) for p in results)
        resp.text = _render_search_results_page(safe_query, results_html)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware:
    """Adds a standard set of security headers to every response."""

    def process_response(self, req, resp, resource, req_succeeded):
        for header_name, header_value in SECURITY_HEADERS.items():
            resp.set_header(header_name, header_value)


# ---------------------------------------------------------------------------
# Application assembly
# ---------------------------------------------------------------------------

def create_app():
    """Build and configure the Falcon application with all routes."""
    application = falcon.App(middleware=[SecurityHeadersMiddleware()])
    application.add_route(ROUTE_PRODUCTS, ProductResource())
    application.add_route(ROUTE_PRODUCT_DETAIL, ProductDetailResource())
    application.add_route(ROUTE_SEARCH, SearchResource())
    return application


app = create_app()


def main():
    """Start the development server for the product catalog app."""
    httpd = simple_server.make_server(SERVER_HOST, SERVER_PORT, app)
    print(f'Server started at http://{SERVER_HOST}:{SERVER_PORT}')
    httpd.serve_forever()


if __name__ == '__main__':
    main()
