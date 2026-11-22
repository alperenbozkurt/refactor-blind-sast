import falcon
import json
import html
from wsgiref import simple_server


CATALOG_PAGE_TEMPLATE = """
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

DETAIL_PAGE_TEMPLATE = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>{name}</title>
            </head>
            <body>
                <h1>{name}</h1>
                <p>Price: ${price}</p>
                <a href="/products">Back to catalog</a>
            </body>
            </html>
        """

SEARCH_NO_RESULTS_TEMPLATE = """
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

SEARCH_RESULTS_TEMPLATE = """
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
            f"<li>{product['name']} - ${product['price']} "
            f"<a href=\"/products/{product['id']}\">View</a></li>"
        )

    def on_get(self, req, resp):
        resp.content_type = 'text/html'
        products_html = ''.join(self._render_item(p) for p in self.products)
        resp.text = CATALOG_PAGE_TEMPLATE.format(products_html=products_html)


class ProductDetailResource:

    @staticmethod
    def _find_product(product_id):
        wanted_id = int(product_id)
        return next(
            (p for p in ProductResource.products if p['id'] == wanted_id),
            None,
        )

    def on_get(self, req, resp, product_id):
        product = self._find_product(product_id)
        if not product:
            raise falcon.HTTPNotFound()
        resp.content_type = 'text/html'
        resp.text = DETAIL_PAGE_TEMPLATE.format(
            name=product['name'],
            price=product['price'],
        )


class SearchResource:

    @staticmethod
    def _render_result(product):
        return f"<li>{product['name']} - ${product['price']}</li>"

    def on_get(self, req, resp):
        query = req.get_param('query', default='')
        lowered_query = query.lower()
        results = [
            p for p in ProductResource.products
            if lowered_query in p['name'].lower()
        ]

        resp.content_type = 'text/html'
        if not results:
            resp.text = SEARCH_NO_RESULTS_TEMPLATE.format(query=query)
            return

        results_html = ''.join(self._render_result(p) for p in results)
        resp.text = SEARCH_RESULTS_TEMPLATE.format(
            query=query,
            results_html=results_html,
        )


app = falcon.App()
app.add_route('/products', ProductResource())
app.add_route('/products/{product_id}', ProductDetailResource())
app.add_route('/search', SearchResource())

if __name__ == '__main__':
    httpd = simple_server.make_server('127.0.0.1', 8000, app)
    httpd.serve_forever()
