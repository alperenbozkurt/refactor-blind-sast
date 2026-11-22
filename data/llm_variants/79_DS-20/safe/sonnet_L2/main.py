import falcon
import html
from wsgiref import simple_server

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

HTML_CONTENT_TYPE = 'text/html'

HOST = '127.0.0.1'
PORT = 8000

ROUTE_PRODUCTS = '/products'
ROUTE_PRODUCT_DETAIL = '/products/{product_id}'
ROUTE_SEARCH = '/search'

SECURITY_HEADERS = (
    ('X-Content-Type-Options', 'nosniff'),
    ('X-Frame-Options', 'DENY'),
    ('X-XSS-Protection', '1; mode=block'),
    ('Content-Security-Policy', "default-src 'self'"),
)

_VIEWPORT_META = '    <meta name="viewport" content="width=device-width, initial-scale=1">'


# --------------------------------------------------------------------------- #
# Template helpers
# --------------------------------------------------------------------------- #

def _build_template(lines, indent):
    """Join template lines using the given indentation, preserving the exact
    whitespace layout of the generated HTML documents."""
    pad = ' ' * indent
    closing_pad = ' ' * (indent - 4)
    return '\n' + '\n'.join(pad + line for line in lines) + '\n' + closing_pad


CATALOG_TEMPLATE = _build_template([
    '<!DOCTYPE html>',
    '<html>',
    '<head>',
    '    <title>Product Catalog</title>',
    _VIEWPORT_META,
    '    <style>',
    '        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}',
    '        .search-box {{ margin: 20px 0; }}',
    '    </style>',
    '</head>',
    '<body>',
    '    <h1>Product Catalog</h1>',
    '    <div class="search-box">',
    '        <form action="/search" method="GET">',
    '            <input type="text" name="query" placeholder="Search products..." required>',
    '            <button type="submit">Search</button>',
    '        </form>',
    '    </div>',
    '    <ul>{products_html}</ul>',
    '</body>',
    '</html>',
], 12)

DETAIL_TEMPLATE = _build_template([
    '<!DOCTYPE html>',
    '<html>',
    '<head>',
    '    <title>{name}</title>',
    _VIEWPORT_META,
    '</head>',
    '<body>',
    '    <h1>{name}</h1>',
    '    <p>Price: ${price}</p>',
    '    <a href="/products">Back to catalog</a>',
    '</body>',
    '</html>',
], 12)

SEARCH_EMPTY_TEMPLATE = _build_template([
    '<!DOCTYPE html>',
    '<html>',
    '<head>',
    '    <title>Search Results</title>',
    _VIEWPORT_META,
    '</head>',
    '<body>',
    '    <h1>Search Results</h1>',
    '    <p>No products found for "{safe_query}"</p>',
    '    <a href="/products">Back to catalog</a>',
    '</body>',
    '</html>',
], 16)

SEARCH_RESULTS_TEMPLATE = _build_template([
    '<!DOCTYPE html>',
    '<html>',
    '<head>',
    '    <title>Search Results</title>',
    _VIEWPORT_META,
    '</head>',
    '<body>',
    '    <h1>Search Results</h1>',
    '    <p>Results for "{safe_query}":</p>',
    '    <ul>{results_html}</ul>',
    '    <a href="/products">Back to catalog</a>',
    '</body>',
    '</html>',
], 12)


def _escape(value):
    """HTML-escape any value after converting it to a string."""
    return html.escape(str(value))


def _render_catalog_item(product):
    return (
        f"<li>{_escape(product['name'])} - ${_escape(product['price'])} "
        f'<a href="/products/{_escape(product["id"])}">View</a></li>'
    )


def _render_search_item(product):
    return f"<li>{_escape(product['name'])} - ${_escape(product['price'])}</li>"


def _set_html(resp, body):
    resp.content_type = HTML_CONTENT_TYPE
    resp.text = body


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
        products_html = ''.join(_render_catalog_item(p) for p in self.products)
        _set_html(resp, CATALOG_TEMPLATE.format(products_html=products_html))


class ProductDetailResource:

    @staticmethod
    def _parse_product_id(raw_id):
        try:
            return int(raw_id)
        except ValueError:
            raise falcon.HTTPBadRequest('Invalid product ID')

    @staticmethod
    def _find_product(product_id):
        return next((p for p in ProductResource.products if p['id'] == product_id), None)

    def on_get(self, req, resp, product_id):
        product_id = self._parse_product_id(product_id)
        product = self._find_product(product_id)
        if not product:
            raise falcon.HTTPNotFound()
        _set_html(resp, DETAIL_TEMPLATE.format(
            name=html.escape(product['name']),
            price=_escape(product['price']),
        ))


class SearchResource:

    @staticmethod
    def _search(query):
        needle = query.lower()
        return [p for p in ProductResource.products if needle in p['name'].lower()]

    def on_get(self, req, resp):
        query = req.get_param('query', default='')
        safe_query = html.escape(query)
        results = self._search(query)
        if not results:
            _set_html(resp, SEARCH_EMPTY_TEMPLATE.format(safe_query=safe_query))
            return
        results_html = ''.join(_render_search_item(p) for p in results)
        _set_html(resp, SEARCH_RESULTS_TEMPLATE.format(
            safe_query=safe_query,
            results_html=results_html,
        ))


# --------------------------------------------------------------------------- #
# Middleware
# --------------------------------------------------------------------------- #

class SecurityHeadersMiddleware:

    def process_response(self, req, resp, resource, req_succeeded):
        for name, value in SECURITY_HEADERS:
            resp.set_header(name, value)


# --------------------------------------------------------------------------- #
# Application wiring
# --------------------------------------------------------------------------- #

app = falcon.App(middleware=[SecurityHeadersMiddleware()])
app.add_route(ROUTE_PRODUCTS, ProductResource())
app.add_route(ROUTE_PRODUCT_DETAIL, ProductDetailResource())
app.add_route(ROUTE_SEARCH, SearchResource())

if __name__ == '__main__':
    httpd = simple_server.make_server(HOST, PORT, app)
    print('Server started at http://127.0.0.1:8000')
    httpd.serve_forever()
