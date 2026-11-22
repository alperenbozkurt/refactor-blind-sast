from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from django.conf import settings
from django.urls import path
from django.core.wsgi import get_wsgi_application
from django.utils.html import escape
import os
import secrets

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
SECRET_KEY_BYTES = 50
TEMPLATE_BACKEND = 'django.template.backends.django.DjangoTemplates'

secret_key = secrets.token_urlsafe(SECRET_KEY_BYTES)


def _build_settings_options(key):
    """Return the keyword arguments used to configure Django settings."""
    return dict(
        DEBUG=False,
        SECRET_KEY=key,
        ROOT_URLCONF=__name__,
        TEMPLATES=[{'BACKEND': TEMPLATE_BACKEND, 'DIRS': []}],
    )


settings.configure(**_build_settings_options(secret_key))

# --------------------------------------------------------------------------- #
# HTML templates
# --------------------------------------------------------------------------- #
HOME_TEMPLATE = (
    '\n            <h1>Welcome to Our Store</h1>\n'
    '            <form action="/search" method="GET">\n'
    '                <input type="text" name="query" placeholder="Search products...">\n'
    '                <button type="submit">Search</button>\n'
    '            </form>\n'
    '            <a href="/products">View All Products</a>\n'
    '        '
)

PRODUCT_LIST_TEMPLATE = (
    '\n            <h1>Our Products</h1>\n'
    '            <ul>{products_html}</ul>\n'
    '            <a href="/">Back to Home</a>\n'
    '        '
)

PRODUCT_LIST_ITEM_TEMPLATE = (
    '<li>{name} - ${price} <a href="/product/{product_id}">View</a></li>'
)

PRODUCT_DETAIL_TEMPLATE = (
    '\n            <h1>{name}</h1>\n'
    '            <p>Price: ${price}</p>\n'
    '            <a href="/products">Back to Products</a>\n'
    '        '
)

SEARCH_EMPTY_TEMPLATE = (
    '\n                <h1>Search Results</h1>\n'
    '                <p>No products found for "<span style="color:red">{query}</span>"</p>\n'
    '                <a href="/products">View All Products</a>\n'
    '            '
)

SEARCH_RESULTS_TEMPLATE = (
    '\n            <h1>Search Results</h1>\n'
    '            <p>Results for "<span style="color:red">{query}</span>":</p>\n'
    '            <ul>{results_html}</ul>\n'
    '            <a href="/products">Back to Products</a>\n'
    '        '
)

SEARCH_RESULT_ITEM_TEMPLATE = '<li>{name} - ${price}</li>'

PRODUCT_NOT_FOUND_MESSAGE = 'Product not found'
NOT_FOUND_STATUS = 404


# --------------------------------------------------------------------------- #
# Domain model and data
# --------------------------------------------------------------------------- #
class Product:

    def __init__(self, id, name, price):
        self.id = id
        self.name = name
        self.price = price


PRODUCTS = [
    Product(1, 'Laptop', 999.99),
    Product(2, 'Phone', 699.99),
    Product(3, 'Tablet', 399.99),
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _escaped_name(product):
    return escape(product.name)


def _escaped_price(product):
    return escape(str(product.price))


def _find_product(product_id):
    return next((p for p in PRODUCTS if p.id == product_id), None)


def _search_products(escaped_query):
    needle = escaped_query.lower()
    return [p for p in PRODUCTS if needle in p.name.lower()]


def _render_product_list_item(product):
    return PRODUCT_LIST_ITEM_TEMPLATE.format(
        name=_escaped_name(product),
        price=_escaped_price(product),
        product_id=product.id,
    )


def _render_search_result_item(product):
    return SEARCH_RESULT_ITEM_TEMPLATE.format(
        name=_escaped_name(product),
        price=_escaped_price(product),
    )


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #
class HomeView(View):

    def get(self, request):
        return HttpResponse(HOME_TEMPLATE)


class ProductListView(View):

    def get(self, request):
        products_html = ''.join(_render_product_list_item(p) for p in PRODUCTS)
        return HttpResponse(
            PRODUCT_LIST_TEMPLATE.format(products_html=products_html)
        )


class ProductDetailView(View):

    def get(self, request, product_id):
        product = _find_product(product_id)
        if not product:
            return HttpResponse(PRODUCT_NOT_FOUND_MESSAGE, status=NOT_FOUND_STATUS)
        return HttpResponse(
            PRODUCT_DETAIL_TEMPLATE.format(
                name=_escaped_name(product),
                price=_escaped_price(product),
            )
        )


class SearchView(View):

    def get(self, request):
        query = escape(request.GET.get('query', ''))
        results = _search_products(query)
        if not results:
            return HttpResponse(SEARCH_EMPTY_TEMPLATE.format(query=query))
        results_html = ''.join(_render_search_result_item(p) for p in results)
        return HttpResponse(
            SEARCH_RESULTS_TEMPLATE.format(query=query, results_html=results_html)
        )


# --------------------------------------------------------------------------- #
# Routing and application
# --------------------------------------------------------------------------- #
urlpatterns = [
    path('', HomeView.as_view()),
    path('products/', ProductListView.as_view()),
    path('product/<int:product_id>/', ProductDetailView.as_view()),
    path('search/', SearchView.as_view()),
]

app = get_wsgi_application()

MANAGEMENT_ARGV = ['manage.py', 'runserver']


def main():
    from django.core.management import execute_from_command_line
    execute_from_command_line(list(MANAGEMENT_ARGV))


if __name__ == '__main__':
    main()
