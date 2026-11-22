import falcon
import html
from wsgiref import simple_server

_CATALOG_TEMPLATE = """
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

_PRODUCT_TEMPLATE = """
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

_SEARCH_RESULTS_TEMPLATE = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Search Results</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
            </head>
            <body>
                <h1>Search Results</h1>
                <p>Results for "{query}":</p>
                <ul>{results_html}</ul>
                <a href="/products">Back to catalog</a>
            </body>
            </html>
        """

_SEARCH_EMPTY_TEMPLATE = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Search Results</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                </head>
                <body>
                    <h1>Search Results</h1>
                    <p>No products found for "{query}"</p>
                    <a href="/products">Back to catalog</a>
                </body>
                </html>
            """


def _product_list_item(product, with_link=False):
    name = html.escape(product['name'])
    price = html.escape(str(product['price']))
    if with_link:
        product_id = html.escape(str(product['id']))
        return f'<li>{name} - ${price} <a href="/products/{product_id}">View</a></li>'
    return f'<li>{name} - ${price}</li>'


class ProductResource:
    products = [
        {'id': 1, 'name': 'Laptop', 'price': 999.99},
        {'id': 2, 'name': 'Smartphone', 'price': 699.99},
        {'id': 3, 'name': 'Tablet', 'price': 399.99},
        {'id': 4, 'name': 'Headphones', 'price': 149.99},
        {'id': 5, 'name': 'Monitor', 'price': 249.99},
    ]

    def on_get(self, req, resp):
        resp.content_type = 'text/html'
        products_html = ''.join(
            _product_list_item(product, with_link=True)
            for product in self.products
        )
        resp.text = _CATALOG_TEMPLATE.format(products_html=products_html)


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
        resp.content_type = 'text/html'
        resp.text = _PRODUCT_TEMPLATE.format(
            name=html.escape(product['name']),
            price=html.escape(str(product['price'])),
        )


class SearchResource:

    def on_get(self, req, resp):
        query = req.get_param('query', default='')
        safe_query = html.escape(query)
        results = [
            product
            for product in ProductResource.products
            if query.lower() in product['name'].lower()
        ]
        resp.content_type = 'text/html'
        if not results:
            resp.text = _SEARCH_EMPTY_TEMPLATE.format(query=safe_query)
            return
        results_html = ''.join(
            _product_list_item(product) for product in results
        )
        resp.text = _SEARCH_RESULTS_TEMPLATE.format(
            query=safe_query,
            results_html=results_html,
        )


class SecurityHeadersMiddleware:
    _HEADERS = (
        ('X-Content-Type-Options', 'nosniff'),
        ('X-Frame-Options', 'DENY'),
        ('X-XSS-Protection', '1; mode=block'),
        ('Content-Security-Policy', "default-src 'self'"),
    )

    def process_response(self, req, resp, resource, req_succeeded):
        for header, value in self._HEADERS:
            resp.set_header(header, value)


app = falcon.App(middleware=[SecurityHeadersMiddleware()])
app.add_route('/products', ProductResource())
app.add_route('/products/{product_id}', ProductDetailResource())
app.add_route('/search', SearchResource())

if __name__ == '__main__':
    httpd = simple_server.make_server('127.0.0.1', 8000, app)
    print('Server started at http://127.0.0.1:8000')
    httpd.serve_forever()
