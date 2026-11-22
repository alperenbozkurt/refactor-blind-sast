import falcon
import html
from wsgiref import simple_server


CATALOG_PAGE_TEMPLATE = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Product Catalog</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                    .search-box {{ margin: 20px 0; }}
                </style>
            </head>
            <body>
                <h1>Product Catalog</h1>
                <div class="search-box">
                    <form action="/search" method="GET">
                        <input type="text" name="query" placeholder="Search products..." required>
                        <button type="submit">Search</button>
                    </form>
                </div>
                <ul>{products_html}</ul>
            </body>
            </html>
        """

PRODUCT_DETAIL_PAGE_TEMPLATE = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>{name}</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
            </head>
            <body>
                <h1>{name}</h1>
                <p>Price: ${price}</p>
                <a href="/products">Back to catalog</a>
            </body>
            </html>
        """

SEARCH_NO_RESULTS_PAGE_TEMPLATE = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Search Results</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                </head>
                <body>
                    <h1>Search Results</h1>
                    <p>No products found for "{safe_query}"</p>
                    <a href="/products">Back to catalog</a>
                </body>
                </html>
            """

SEARCH_RESULTS_PAGE_TEMPLATE = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Search Results</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
            </head>
            <body>
                <h1>Search Results</h1>
                <p>Results for "{safe_query}":</p>
                <ul>{results_html}</ul>
                <a href="/products">Back to catalog</a>
            </body>
            </html>
        """

SECURITY_HEADERS = (
    ('X-Content-Type-Options', 'nosniff'),
    ('X-Frame-Options', 'DENY'),
    ('X-XSS-Protection', '1; mode=block'),
    ('Content-Security-Policy', "default-src 'self'"),
)


def _escape(value):
    """Escape any value for safe inclusion in HTML."""
    return html.escape(str(value))


def _send_html(resp, body):
    resp.content_type = 'text/html'
    resp.text = body


class ProductResource:
    products = [
        {'id': 1, 'name': 'Laptop', 'price': 999.99},
        {'id': 2, 'name': 'Smartphone', 'price': 699.99},
        {'id': 3, 'name': 'Tablet', 'price': 399.99},
        {'id': 4, 'name': 'Headphones', 'price': 149.99},
        {'id': 5, 'name': 'Monitor', 'price': 249.99},
    ]

    @staticmethod
    def _render_item(product):
        return (
            f"<li>{_escape(product['name'])} - ${_escape(product['price'])} "
            f'<a href="/products/{_escape(product["id"])}">View</a></li>'
        )

    def on_get(self, req, resp):
        products_html = ''.join(self._render_item(p) for p in self.products)
        _send_html(resp, CATALOG_PAGE_TEMPLATE.format(products_html=products_html))


class ProductDetailResource:

    def on_get(self, req, resp, product_id):
        try:
            product_id = int(product_id)
        except ValueError:
            raise falcon.HTTPBadRequest('Invalid product ID')

        product = next(
            (p for p in ProductResource.products if p['id'] == product_id),
            None,
        )
        if not product:
            raise falcon.HTTPNotFound()

        _send_html(
            resp,
            PRODUCT_DETAIL_PAGE_TEMPLATE.format(
                name=_escape(product['name']),
                price=_escape(product['price']),
            ),
        )


class SearchResource:

    @staticmethod
    def _render_result(product):
        return f"<li>{_escape(product['name'])} - ${_escape(product['price'])}</li>"

    def on_get(self, req, resp):
        query = req.get_param('query', default='')
        safe_query = html.escape(query)
        results = [
            p for p in ProductResource.products
            if query.lower() in p['name'].lower()
        ]

        if not results:
            _send_html(
                resp,
                SEARCH_NO_RESULTS_PAGE_TEMPLATE.format(safe_query=safe_query),
            )
            return

        results_html = ''.join(self._render_result(p) for p in results)
        _send_html(
            resp,
            SEARCH_RESULTS_PAGE_TEMPLATE.format(
                safe_query=safe_query,
                results_html=results_html,
            ),
        )


class SecurityHeadersMiddleware:

    def process_response(self, req, resp, resource, req_succeeded):
        for name, value in SECURITY_HEADERS:
            resp.set_header(name, value)


app = falcon.App(middleware=[SecurityHeadersMiddleware()])
app.add_route('/products', ProductResource())
app.add_route('/products/{product_id}', ProductDetailResource())
app.add_route('/search', SearchResource())

if __name__ == '__main__':
    httpd = simple_server.make_server('127.0.0.1', 8000, app)
    print('Server started at http://127.0.0.1:8000')
    httpd.serve_forever()
