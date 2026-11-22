from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import math
import os
from enum import Enum

# --------------------------------------------------------------------------- #
# Configuration constants
# --------------------------------------------------------------------------- #
TEMPLATES_DIR = 'templates'
FORM_TEMPLATE_NAME = 'form.html'
FORM_TEMPLATE_PATH = 'templates/form.html'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

MIN_DISCOUNT = 0
MAX_DISCOUNT = 0.9

BULK_RATE_PER_UNIT = 0.01
BULK_MAX_DISCOUNT = 0.5

SEASONAL_QUANTITY_THRESHOLD = 10
SEASONAL_HIGH_DISCOUNT = 0.2
SEASONAL_LOW_DISCOUNT = 0.1

LOYALTY_LOG_FACTOR = 0.1

DEFAULT_BASE_PRICE = 0

PRICE_DECIMAL_PLACES = 2

FORM_TEMPLATE_HTML = '\n        <!DOCTYPE html>\n        <html>\n        <head><title>Dynamic Pricing Calculator</title></head>\n        <body>\n            <h1>Product Pricing Calculator</h1>\n            <form method="post" action="/calculate">\n                Product Type: \n                <select name="product_type">\n                    {% for pt in product_types %}\n                    <option value="{{ pt }}">{{ pt|title }}</option>\n                    {% endfor %}\n                </select><br>\n                Quantity: <input type="number" name="quantity" min="1" value="1"><br>\n                Discount Type:\n                <select name="discount_type">\n                    {% for dt in discount_types %}\n                    <option value="{{ dt }}">{{ dt|title }}</option>\n                    {% endfor %}\n                </select><br>\n                <button type="submit">Calculate</button>\n            </form>\n        </body>\n        </html>\n        '

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# --------------------------------------------------------------------------- #
# Domain enums
# --------------------------------------------------------------------------- #
class ProductType(str, Enum):
    PREMIUM = 'premium'
    STANDARD = 'standard'
    ECONOMY = 'economy'


class DiscountType(str, Enum):
    BULK = 'bulk'
    SEASONAL = 'seasonal'
    LOYALTY = 'loyalty'


# --------------------------------------------------------------------------- #
# Discount strategies
# --------------------------------------------------------------------------- #
def _bulk_discount(quantity):
    return min(BULK_MAX_DISCOUNT, quantity * BULK_RATE_PER_UNIT)


def _seasonal_discount(quantity):
    if quantity > SEASONAL_QUANTITY_THRESHOLD:
        return SEASONAL_HIGH_DISCOUNT
    return SEASONAL_LOW_DISCOUNT


def _loyalty_discount(quantity):
    return math.log(quantity + 1) * LOYALTY_LOG_FACTOR


def _default_base_prices():
    return {
        ProductType.PREMIUM: 100,
        ProductType.STANDARD: 50,
        ProductType.ECONOMY: 20,
    }


def _default_discount_functions():
    return {
        DiscountType.BULK: _bulk_discount,
        DiscountType.SEASONAL: _seasonal_discount,
        DiscountType.LOYALTY: _loyalty_discount,
    }


def _clamp_discount(discount):
    return max(MIN_DISCOUNT, min(MAX_DISCOUNT, discount))


# --------------------------------------------------------------------------- #
# Pricing engine
# --------------------------------------------------------------------------- #
class PricingEngine:

    def __init__(self):
        self.base_prices = _default_base_prices()
        self.discount_functions = _default_discount_functions()

    def _validate_quantity(self, quantity):
        if quantity <= 0:
            raise ValueError('Quantity must be positive')

    def _resolve_discount_function(self, discount_type):
        discount_func = self.discount_functions.get(discount_type)
        if not discount_func:
            raise ValueError('Invalid discount type')
        return discount_func

    def calculate(self, product_type: ProductType, discount_type: DiscountType, quantity: int):
        try:
            self._validate_quantity(quantity)
            base_price = self.base_prices.get(product_type, DEFAULT_BASE_PRICE)
            discount_func = self._resolve_discount_function(discount_type)
            discount = _clamp_discount(discount_func(quantity))
            return base_price * quantity * (1 - discount)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


@app.get('/', response_class=HTMLResponse)
async def calculator_form(request: Request):
    return templates.TemplateResponse(
        FORM_TEMPLATE_NAME,
        {
            'request': request,
            'product_types': _enum_values(ProductType),
            'discount_types': _enum_values(DiscountType),
        },
    )


@app.post('/calculate')
async def calculate_price(product_type: ProductType=Form(...), discount_type: DiscountType=Form(...), quantity: int=Form(..., gt=0)):
    engine = PricingEngine()
    try:
        total = engine.calculate(product_type, discount_type, quantity)
        return {'product': product_type.value, 'total_price': round(total, PRICE_DECIMAL_PLACES)}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail='Calculation error')


# --------------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------------- #
def _write_form_template():
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    with open(FORM_TEMPLATE_PATH, 'w') as f:
        f.write(FORM_TEMPLATE_HTML)


def main():
    import uvicorn
    _write_form_template()
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
