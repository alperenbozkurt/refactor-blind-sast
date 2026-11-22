import os
import secrets

from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path
from django.utils.html import escape
from django.views import View

secret_key = secrets.token_urlsafe(50)

settings.configure(
    DEBUG=False,
    SECRET_KEY=secret_key,
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


class HomeView(View):

    def get(self, request):
        return HttpResponse(
            '\n'
            '            <h1>Welcome to Our Store</h1>\n'
            '            <form action="/search" method="GET">\n'
            '                <input type="text" name="query" '
            'placeholder="Search products...">\n'
            '                <button type="submit">Search</button>\n'
            '            </form>\n'
            '            <a href="/products">View All Products</a>\n'
            '        '
        )


class ProductListView(View):

    def get(self, request):
        products_html = ''.join(
            f'<li>{escape(p.name)} - ${escape(str(p.price))} '
            f'<a href="/product/{p.id}">View</a></li>'
            for p in PRODUCTS
        )
        return HttpResponse(
            '\n'
            '            <h1>Our Products</h1>\n'
            f'            <ul>{products_html}</ul>\n'
            '            <a href="/">Back to Home</a>\n'
            '        '
        )


class ProductDetailView(View):

    def get(self, request, product_id):
        product = next((p for p in PRODUCTS if p.id == product_id), None)
        if not product:
            return HttpResponse('Product not found', status=404)
        return HttpResponse(
            '\n'
            f'            <h1>{escape(product.name)}</h1>\n'
            f'            <p>Price: ${escape(str(product.price))}</p>\n'
            '            <a href="/products">Back to Products</a>\n'
            '        '
        )


class SearchView(View):

    def get(self, request):
        query = escape(request.GET.get('query', ''))
        results = [p for p in PRODUCTS if query.lower() in p.name.lower()]
        if not results:
            return HttpResponse(
                '\n'
                '                <h1>Search Results</h1>\n'
                f'                <p>No products found for '
                f'"<span style="color:red">{query}</span>"</p>\n'
                '                <a href="/products">View All Products</a>\n'
                '            '
            )
        results_html = ''.join(
            f'<li>{escape(p.name)} - ${escape(str(p.price))}</li>'
            for p in results
        )
        return HttpResponse(
            '\n'
            '            <h1>Search Results</h1>\n'
            f'            <p>Results for '
            f'"<span style="color:red">{query}</span>":</p>\n'
            f'            <ul>{results_html}</ul>\n'
            '            <a href="/products">Back to Products</a>\n'
            '        '
        )


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
