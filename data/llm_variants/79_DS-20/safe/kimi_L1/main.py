import falcon
import html
from wsgiref import simple_server


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
        product_items = []
        for product in self.products:
            name = html.escape(product['name'])
            price = html.escape(str(product['price']))
            product_id = html.escape(str(product['id']))
            product_items.append(
                f'<li>{name} - ${price} <a href="/products/{product_id}">View</a></li>'
            )
        products_html = ''.join(product_items)
        resp.text = (
            '\n'
            '            <!DOCTYPE html>\n'
            '            <html>\n'
            '            <head>\n'
            '                <title>Product Catalog</title>\n'
            '                <meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '                <style>\n'
            '                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }\n'
            '                    .search-box { margin: 20px 0; }\n'
            '                </style>\n'
            '            </head>\n'
            '            <body>\n'
            '                <h1>Product Catalog</h1>\n'
            '                <div class="search-box">\n'
            '                    <form action="/search" method="GET">\n'
            '                        <input type="text" name="query" placeholder="Search products..." required>\n'
            '                        <button type="submit">Search</button>\n'
            '                    </form>\n'
            '                </div>\n'
            f'                <ul>{products_html}</ul>\n'
            '            </body>\n'
            '            </html>\n'
            '        '
        )


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
        product_name = html.escape(product['name'])
        product_price = html.escape(str(product['price']))
        resp.text = (
            '\n'
            '            <!DOCTYPE html>\n'
            '            <html>\n'
            '            <head>\n'
            f'                <title>{product_name}</title>\n'
            '                <meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '            </head>\n'
            '            <body>\n'
            f'                <h1>{product_name}</h1>\n'
            f'                <p>Price: ${product_price}</p>\n'
            '                <a href="/products">Back to catalog</a>\n'
            '            </body>\n'
            '            </html>\n'
            '        '
        )


class SearchResource:

    def on_get(self, req, resp):
        query = req.get_param('query', default='')
        safe_query = html.escape(query)
        results = [
            p
            for p in ProductResource.products
            if query.lower() in p['name'].lower()
        ]

        if not results:
            resp.content_type = 'text/html'
            resp.text = (
                '\n'
                '                <!DOCTYPE html>\n'
                '                <html>\n'
                '                <head>\n'
                '                    <title>Search Results</title>\n'
                '                    <meta name="viewport" content="width=device-width, initial-scale=1">\n'
                '                </head>\n'
                '                <body>\n'
                '                    <h1>Search Results</h1>\n'
                f'                    <p>No products found for "{safe_query}"</p>\n'
                '                    <a href="/products">Back to catalog</a>\n'
                '                </body>\n'
                '                </html>\n'
                '            '
            )
            return

        result_items = []
        for product in results:
            name = html.escape(product['name'])
            price = html.escape(str(product['price']))
            result_items.append(f'<li>{name} - ${price}</li>')
        results_html = ''.join(result_items)

        resp.content_type = 'text/html'
        resp.text = (
            '\n'
            '            <!DOCTYPE html>\n'
            '            <html>\n'
            '            <head>\n'
            '                <title>Search Results</title>\n'
            '                <meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '            </head>\n'
            '            <body>\n'
            '                <h1>Search Results</h1>\n'
            f'                <p>Results for "{safe_query}":</p>\n'
            f'                <ul>{results_html}</ul>\n'
            '                <a href="/products">Back to catalog</a>\n'
            '            </body>\n'
            '            </html>\n'
            '        '
        )


class SecurityHeadersMiddleware:

    def process_response(self, req, resp, resource, req_succeeded):
        resp.set_header('X-Content-Type-Options', 'nosniff')
        resp.set_header('X-Frame-Options', 'DENY')
        resp.set_header('X-XSS-Protection', '1; mode=block')
        resp.set_header('Content-Security-Policy', "default-src 'self'")


app = falcon.App(middleware=[SecurityHeadersMiddleware()])
app.add_route('/products', ProductResource())
app.add_route('/products/{product_id}', ProductDetailResource())
app.add_route('/search', SearchResource())

if __name__ == '__main__':
    httpd = simple_server.make_server('127.0.0.1', 8000, app)
    print('Server started at http://127.0.0.1:8000')
    httpd.serve_forever()
