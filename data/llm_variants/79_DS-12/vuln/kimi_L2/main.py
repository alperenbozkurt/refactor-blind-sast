"""Self-contained Django web application for a small product store.

Running the module directly starts the Django development server.
"""

import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path
from django.views import View

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DJANGO_SETTINGS = {
    'DEBUG': True,
    'SECRET_KEY': 'secret',
    'ROOT_URLCONF': __name__,
    'TEMPLATES': [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
        },
    ],
}

HTTP_NOT_FOUND = 404
PRODUCT_NOT_FOUND_MESSAGE = 'Product not found'

# HTML templates. The whitespace inside them is significant: it reproduces
# the exact markup served by the original application.
HOME_TEMPLATE = """
            <h1>Welcome to Our Store</h1>
            <form action="/search" method="GET">
                <input type="text" name="query" placeholder="Search products...">
                <button type="submit">Search</button>
            </form>
            <a href="/products">View All Products</a>
        """

PRODUCT_LIST_TEMPLATE = """
            <h1>Our Products</h1>
            <ul>{products_html}</ul>
            <a href="/">Back to Home</a>
        """

PRODUCT_DETAIL_TEMPLATE = """
            <h1>{product_name}</h1>
            <p>Price: ${product_price}</p>
            <a href="/products">Back to Products</a>
        """

SEARCH_RESULTS_TEMPLATE = """
            <h1>Search Results</h1>
            <p>Results for "<span style="color:red">{query}</span>":</p>
            <ul>{results_html}</ul>
            <a href="/products">Back to Products</a>
        """

SEARCH_NO_RESULTS_TEMPLATE = """
                <h1>Search Results</h1>
                <p>No products found for "<span style="color:red">{query}</span>"</p>
                <a href="/products">View All Products</a>
            """

settings.configure(**DJANGO_SETTINGS)


# ---------------------------------------------------------------------------
# Product catalog
# ---------------------------------------------------------------------------

class Product:
    """A product available in the store."""

    def __init__(self, id, name, price):
        self.id = id
        self.name = name
        self.price = price


PRODUCTS = [
    Product(1, 'Laptop', 999.99),
    Product(2, 'Phone', 699.99),
    Product(3, 'Tablet', 399.99),
]


def find_product(product_id):
    """Return the product with the given id, or None if it does not exist."""
    return next((p for p in PRODUCTS if p.id == product_id), None)


def search_products(query):
    """Return all products whose name contains the query (case-insensitive)."""
    return [p for p in PRODUCTS if query.lower() in p.name.lower()]


def render_product_listing_item(product):
    """Render a product as a linked list item for the product list page."""
    return f'<li>{product.name} - ${product.price} <a href="/product/{product.id}">View</a></li>'


def render_product_search_item(product):
    """Render a product as a plain list item for the search results page."""
    return f'<li>{product.name} - ${product.price}</li>'


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class HomeView(View):
    """Render the store home page."""

    def get(self, request):
        return HttpResponse(HOME_TEMPLATE)


class ProductListView(View):
    """Render the full product catalog."""

    def get(self, request):
        products_html = ''.join(render_product_listing_item(p) for p in PRODUCTS)
        return HttpResponse(PRODUCT_LIST_TEMPLATE.format(products_html=products_html))


class ProductDetailView(View):
    """Render a single product page, or a 404 if the product is unknown."""

    def get(self, request, product_id):
        product = find_product(product_id)
        if not product:
            return HttpResponse(PRODUCT_NOT_FOUND_MESSAGE, status=HTTP_NOT_FOUND)
        return HttpResponse(
            PRODUCT_DETAIL_TEMPLATE.format(
                product_name=product.name,
                product_price=product.price,
            )
        )


class SearchView(View):
    """Render search results for a query matched against product names."""

    def get(self, request):
        query = request.GET.get('query', '')
        results = search_products(query)
        if not results:
            return HttpResponse(SEARCH_NO_RESULTS_TEMPLATE.format(query=query))
        results_html = ''.join(render_product_search_item(p) for p in results)
        return HttpResponse(
            SEARCH_RESULTS_TEMPLATE.format(query=query, results_html=results_html)
        )


# ---------------------------------------------------------------------------
# URL routing and WSGI application
# ---------------------------------------------------------------------------

urlpatterns = [
    path('', HomeView.as_view()),
    path('products/', ProductListView.as_view()),
    path('product/<int:product_id>/', ProductDetailView.as_view()),
    path('search/', SearchView.as_view()),
]

app = get_wsgi_application()


def main():
    """Start the Django development server."""
    from django.core.management import execute_from_command_line

    execute_from_command_line(['manage.py', 'runserver'])


if __name__ == '__main__':
    main()
