import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path
from django.views import View

settings.configure(
    DEBUG=True,
    SECRET_KEY='secret',
    ROOT_URLCONF=__name__,
    TEMPLATES=[
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
        }
    ],
)


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


def _find_product(product_id):
    """Return the product with the given id, or None if it doesn't exist."""
    return next((p for p in PRODUCTS if p.id == product_id), None)


def _product_list_item(product):
    return f'<li>{product.name} - ${product.price} <a href="/product/{product.id}">View</a></li>'


def _search_result_item(product):
    return f'<li>{product.name} - ${product.price}</li>'


_HOME_PAGE = (
    '\n            <h1>Welcome to Our Store</h1>'
    '\n            <form action="/search" method="GET">'
    '\n                <input type="text" name="query" placeholder="Search products...">'
    '\n                <button type="submit">Search</button>'
    '\n            </form>'
    '\n            <a href="/products">View All Products</a>'
    '\n        '
)


def _product_list_page(products_html):
    return (
        '\n            <h1>Our Products</h1>'
        f'\n            <ul>{products_html}</ul>'
        '\n            <a href="/">Back to Home</a>'
        '\n        '
    )


def _product_detail_page(product):
    return (
        f'\n            <h1>{product.name}</h1>'
        f'\n            <p>Price: ${product.price}</p>'
        '\n            <a href="/products">Back to Products</a>'
        '\n        '
    )


def _empty_search_page(query):
    return (
        '\n                <h1>Search Results</h1>'
        f'\n                <p>No products found for "<span style="color:red">{query}</span>"</p>'
        '\n                <a href="/products">View All Products</a>'
        '\n            '
    )


def _search_results_page(query, results_html):
    return (
        '\n            <h1>Search Results</h1>'
        f'\n            <p>Results for "<span style="color:red">{query}</span>":</p>'
        f'\n            <ul>{results_html}</ul>'
        '\n            <a href="/products">Back to Products</a>'
        '\n        '
    )


class HomeView(View):

    def get(self, request):
        return HttpResponse(_HOME_PAGE)


class ProductListView(View):

    def get(self, request):
        products_html = ''.join(_product_list_item(p) for p in PRODUCTS)
        return HttpResponse(_product_list_page(products_html))


class ProductDetailView(View):

    def get(self, request, product_id):
        product = _find_product(product_id)
        if not product:
            return HttpResponse('Product not found', status=404)
        return HttpResponse(_product_detail_page(product))


class SearchView(View):

    def get(self, request):
        query = request.GET.get('query', '')
        results = [p for p in PRODUCTS if query.lower() in p.name.lower()]
        if not results:
            return HttpResponse(_empty_search_page(query))
        results_html = ''.join(_search_result_item(p) for p in results)
        return HttpResponse(_search_results_page(query, results_html))


urlpatterns = [
    path('', HomeView.as_view()),
    path('products/', ProductListView.as_view()),
    path('product/<int:product_id>/', ProductDetailView.as_view()),
    path('search/', SearchView.as_view()),
]

app = get_wsgi_application()

if __name__ == '__main__':
    from django.core.management import execute_from_command_line

    execute_from_command_line(['manage.py', 'runserver'])
