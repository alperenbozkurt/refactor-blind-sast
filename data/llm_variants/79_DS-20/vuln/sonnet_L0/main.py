import falcon
import json
import html
from wsgiref import simple_server


def _product_list_item(product, with_link=False):
    item = f"{product['name']} - ${product['price']}"
    if with_link:
        item += f""" <a href="/products/{product['id']}">View</a>"""
    return f"<li>{item}</li>"


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
            _product_list_item(p, with_link=True) for p in self.products
        )
        resp.text = (
            '\n            <!DOCTYPE html>\n            <html>\n            <head>\n'
            '                <title>Product Catalog</title>\n'
            '                <style>\n'
            '                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }\n'
            '                    .search-box { margin: 20px 0; }\n'
            '                </style>\n'
            '            </head>\n            <body>\n'
            '                <h1>Product Catalog</h1>\n'
            '                <div class="search-box">\n'
            '                    <form action="/search" method="GET">\n'
            '                        <input type="text" name="query" placeholder="Search products...">\n'
            '                        <button type="submit">Search</button>\n'
            '                    </form>\n'
            '                </div>\n'
            f'                <ul>{products_html}</ul>\n'
            '            </body>\n            </html>\n        '
        )


class ProductDetailResource:

    def on_get(self, req, resp, product_id):
        product_id = int(product_id)
        product = next(
            (p for p in ProductResource.products if p['id'] == product_id),
            None,
        )
        if not product:
            raise falcon.HTTPNotFound()
        resp.content_type = 'text/html'
        resp.text = (
            '\n            <!DOCTYPE html>\n            <html>\n            <head>\n'
            f"                <title>{product['name']}</title>\n"
            '            </head>\n            <body>\n'
            f"                <h1>{product['name']}</h1>\n"
            f"                <p>Price: ${product['price']}</p>\n"
            '                <a href="/products">Back to catalog</a>\n'
            '            </body>\n            </html>\n        '
        )


class SearchResource:

    def on_get(self, req, resp):
        query = req.get_param('query', default='')
        needle = query.lower()
        results = [
            p for p in ProductResource.products
            if needle in p['name'].lower()
        ]
        # Escape user-supplied input before reflecting it into the HTML.
        safe_query = html.escape(query)
        resp.content_type = 'text/html'

        if not results:
            resp.text = (
                '\n                <!DOCTYPE html>\n                <html>\n                <head>\n'
                '                    <title>Search Results</title>\n'
                '                </head>\n                <body>\n'
                '                    <h1>Search Results</h1>\n'
                f'                    <p>No products found for "{safe_query}"</p>\n'
                '                    <a href="/products">Back to catalog</a>\n'
                '                </body>\n                </html>\n            '
            )
            return

        results_html = ''.join(_product_list_item(p) for p in results)
        resp.text = (
            '\n            <!DOCTYPE html>\n            <html>\n            <head>\n'
            '                <title>Search Results</title>\n'
            '            </head>\n            <body>\n'
            '                <h1>Search Results</h1>\n'
            f'                <p>Results for "{safe_query}":</p>\n'
            f'                <ul>{results_html}</ul>\n'
            '                <a href="/products">Back to catalog</a>\n'
            '            </body>\n            </html>\n        '
        )


app = falcon.App()
app.add_route('/products', ProductResource())
app.add_route('/products/{product_id}', ProductDetailResource())
app.add_route('/search', SearchResource())

if __name__ == '__main__':
    httpd = simple_server.make_server('127.0.0.1', 8000, app)
    httpd.serve_forever()
