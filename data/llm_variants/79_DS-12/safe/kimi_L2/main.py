"""Self-contained Django application for browsing and searching a product catalog."""

import os  # noqa: F401 -- kept as part of the module's public interface
import secrets

from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse
from django.shortcuts import render  # noqa: F401 -- kept as part of the module's public interface
from django.urls import path
from django.utils.html import escape
from django.views import View

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_SECRET_KEY_NBYTES = 50

_DJANGO_SETTINGS = {
    'DEBUG': False,
    'ROOT_URLCONF': __name__,
    'TEMPLATES': [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
        },
    ],
}

_HTTP_NOT_FOUND = 404
_PRODUCT_NOT_FOUND_MESSAGE = 'Product not found'

_HOME_PAGE = '''
            <h1>Welcome to Our Store</h1>
            <form action="/search" method="GET">
                <input type="text" name="query" placeholder="Search products...">
                <button type="submit">Search</button>
            </form>
            <a href="/products">View All Products</a>
        '''

_PRODUCT_LIST_PAGE = '''
            <h1>Our Products</h1>
            <ul>{products_html}</ul>
            <a href="/">Back to Home</a>
        '''

_PRODUCT_DETAIL_PAGE = '''
            <h1>{name}</h1>
            <p>Price: ${price}</p>
            <a href="/products">Back to Products</a>
        '''

_SEARCH_RESULTS_PAGE = '''
            <h1>Search Results</h1>
            <p>Results for "<span style="color:red">{query}</span>":</p>
            <ul>{results_html}</ul>
            <a href="/products">Back to Products</a>
        '''

_SEARCH_NO_RESULTS_PAGE = '''
                <h1>Search Results</h1>
                <p>No products found for "<span style="color:red">{query}</span>"</p>
                <a href="/products">View All Products</a>
            '''


def _configure_settings(secret_key):
    """Configure Django settings for this standalone module."""
    settings.configure(SECRET_KEY=secret_key, **_DJANGO_SETTINGS)


secret_key = secrets.token_urlsafe(_SECRET_KEY_NBYTES)
_configure_settings(secret_key)


# ---------------------------------------------------------------------------
# Domain model and catalog
# ---------------------------------------------------------------------------

class Product:

    def __init__(self, id, name, price):
        self.id = id
        self.name = name
        self.price = price


_PRODUCT_DATA = (
    (1, 'Laptop', 999.99),
    (2, 'Phone', 699.99),
    (3, 'Tablet', 399.99),
)

PRODUCTS = [Product(product_id, name, price) for product_id, name, price in _PRODUCT_DATA]


def _find_product(product_id):
    """Return the product with the given id, or None when it does not exist."""
    return next((product for product in PRODUCTS if product.id == product_id), None)


def _search_products(query):
    """Return the products whose name contains the given (already escaped) query."""
    return [product for product in PRODUCTS if query.lower() in product.name.lower()]


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render_product_list_item(product):
    """Render a product as an item of the product list page."""
    return (
        f'<li>{escape(product.name)} - ${escape(str(product.price))} '
        f'<a href="/product/{product.id}">View</a></li>'
    )


def _render_search_result_item(product):
    """Render a product as an item of the search results page."""
    return f'<li>{escape(product.name)} - ${escape(str(product.price))}</li>'


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class HomeView(View):

    def get(self, request):
        return HttpResponse(_HOME_PAGE)


class ProductListView(View):

    def get(self, request):
        products_html = ''.join(
            _render_product_list_item(product) for product in PRODUCTS
        )
        return HttpResponse(_PRODUCT_LIST_PAGE.format(products_html=products_html))


class ProductDetailView(View):

    def get(self, request, product_id):
        product = _find_product(product_id)
        if not product:
            return HttpResponse(_PRODUCT_NOT_FOUND_MESSAGE, status=_HTTP_NOT_FOUND)
        return HttpResponse(
            _PRODUCT_DETAIL_PAGE.format(
                name=escape(product.name),
                price=escape(str(product.price)),
            )
        )


class SearchView(View):

    def get(self, request):
        query = escape(request.GET.get('query', ''))
        results = _search_products(query)
        if not results:
            return HttpResponse(_SEARCH_NO_RESULTS_PAGE.format(query=query))
        results_html = ''.join(
            _render_search_result_item(product) for product in results
        )
        return HttpResponse(_SEARCH_RESULTS_PAGE.format(query=query, results_html=results_html))


# ---------------------------------------------------------------------------
# URL routing and WSGI entry point
# ---------------------------------------------------------------------------

urlpatterns = [
    path('', HomeView.as_view()),
    path('products/', ProductListView.as_view()),
    path('product/<int:product_id>/', ProductDetailView.as_view()),
    path('search/', SearchView.as_view()),
]

app = get_wsgi_application()


def main():
    """Run the development server (command-line entry point)."""
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', 'runserver'])


if __name__ == '__main__':
    main()
