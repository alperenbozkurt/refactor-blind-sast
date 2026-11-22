from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from django.conf import settings
from django.urls import path
from django.core.wsgi import get_wsgi_application
import os

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

    def __init__(self, id, name, price):
        self.id = id
        self.name = name
        self.price = price


PRODUCTS = [
    Product(1, 'Laptop', 999.99),
    Product(2, 'Phone', 699.99),
    Product(3, 'Tablet', 399.99),
]


# --- HTML templates -------------------------------------------------------

HOME_TEMPLATE = (
    '\n'
    '            <h1>Welcome to Our Store</h1>\n'
    '            <form action="/search" method="GET">\n'
    '                <input type="text" name="query" placeholder="Search products...">\n'
    '                <button type="submit">Search</button>\n'
    '            </form>\n'
    '            <a href="/products">View All Products</a>\n'
    '        '
)

PRODUCT_LIST_TEMPLATE = (
    '\n'
    '            <h1>Our Products</h1>\n'
    '            <ul>{products_html}</ul>\n'
    '            <a href="/">Back to Home</a>\n'
    '        '
)

PRODUCT_LIST_ITEM_TEMPLATE = '<li>{name} - ${price} <a href="/product/{id}">View</a></li>'

PRODUCT_DETAIL_TEMPLATE = (
    '\n'
    '            <h1>{name}</h1>\n'
    '            <p>Price: ${price}</p>\n'
    '            <a href="/products">Back to Products</a>\n'
    '        '
)

SEARCH_NO_RESULTS_TEMPLATE = (
    '\n'
    '                <h1>Search Results</h1>\n'
    '                <p>No products found for "<span style="color:red">{query}</span>"</p>\n'
    '                <a href="/products">View All Products</a>\n'
    '            '
)

SEARCH_RESULTS_TEMPLATE = (
    '\n'
    '            <h1>Search Results</h1>\n'
    '            <p>Results for "<span style="color:red">{query}</span>":</p>\n'
    '            <ul>{results_html}</ul>\n'
    '            <a href="/products">Back to Products</a>\n'
    '        '
)

SEARCH_RESULT_ITEM_TEMPLATE = '<li>{name} - ${price}</li>'


# --- Views ----------------------------------------------------------------

class HomeView(View):

    def get(self, request):
        return HttpResponse(HOME_TEMPLATE)


class ProductListView(View):

    def get(self, request):
        products_html = ''.join(
            PRODUCT_LIST_ITEM_TEMPLATE.format(name=p.name, price=p.price, id=p.id)
            for p in PRODUCTS
        )
        return HttpResponse(PRODUCT_LIST_TEMPLATE.format(products_html=products_html))


class ProductDetailView(View):

    def get(self, request, product_id):
        product = next((p for p in PRODUCTS if p.id == product_id), None)
        if not product:
            return HttpResponse('Product not found', status=404)
        return HttpResponse(
            PRODUCT_DETAIL_TEMPLATE.format(name=product.name, price=product.price)
        )


class SearchView(View):

    def get(self, request):
        query = request.GET.get('query', '')
        results = [p for p in PRODUCTS if query.lower() in p.name.lower()]
        if not results:
            return HttpResponse(SEARCH_NO_RESULTS_TEMPLATE.format(query=query))
        results_html = ''.join(
            SEARCH_RESULT_ITEM_TEMPLATE.format(name=p.name, price=p.price)
            for p in results
        )
        return HttpResponse(
            SEARCH_RESULTS_TEMPLATE.format(query=query, results_html=results_html)
        )


# --- URL configuration / WSGI ---------------------------------------------

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
