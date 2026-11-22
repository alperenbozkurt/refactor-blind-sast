"""A small product catalog web application built with Falcon."""

# The ``html`` and ``json`` imports are unused, but they are kept so that the
# existing module-level names remain available.
import html
import json
from wsgiref import simple_server

import falcon


class ProductResource:
    """Serves the catalog page listing all products."""

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
            f'<li>{product["name"]} - ${product["price"]} '
            f'<a href="/products/{product["id"]}">View</a></li>'
            for product in self.products
        )
        resp.text = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Product Catalog</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                    .search-box {{ margin: 20px 0; }}
                </style>
            </head>
            <body>
                <h1>Product Catalog</h1>
                <div class="search-box">
                    <form action="/search" method="GET">
                        <input type="text" name="query" placeholder="Search products...">
                        <button type="submit">Search</button>
                    </form>
                </div>
                <ul>{products_html}</ul>
            </body>
            </html>
        """


class ProductDetailResource:
    """Serves the detail page for a single product."""

    def on_get(self, req, resp, product_id):
        product = next(
            (
                item
                for item in ProductResource.products
                if item['id'] == int(product_id)
            ),
            None,
        )
        if not product:
            raise falcon.HTTPNotFound()
        resp.content_type = 'text/html'
        resp.text = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{product['name']}</title>
            </head>
            <body>
                <h1>{product['name']}</h1>
                <p>Price: ${product['price']}</p>
                <a href="/products">Back to catalog</a>
            </body>
            </html>
        """


class SearchResource:
    """Serves product search results."""

    def on_get(self, req, resp):
        query = req.get_param('query', default='')
        results = [
            product
            for product in ProductResource.products
            if query.lower() in product['name'].lower()
        ]
        resp.content_type = 'text/html'
        if not results:
            resp.text = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Search Results</title>
                </head>
                <body>
                    <h1>Search Results</h1>
                    <p>No products found for "{query}"</p>
                    <a href="/products">Back to catalog</a>
                </body>
                </html>
            """
            return
        results_html = ''.join(
            f'<li>{product["name"]} - ${product["price"]}</li>'
            for product in results
        )
        resp.text = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Search Results</title>
            </head>
            <body>
                <h1>Search Results</h1>
                <p>Results for "{query}":</p>
                <ul>{results_html}</ul>
                <a href="/products">Back to catalog</a>
            </body>
            </html>
        """


app = falcon.App()
app.add_route('/products', ProductResource())
app.add_route('/products/{product_id}', ProductDetailResource())
app.add_route('/search', SearchResource())

if __name__ == '__main__':
    httpd = simple_server.make_server('127.0.0.1', 8000, app)
    httpd.serve_forever()
