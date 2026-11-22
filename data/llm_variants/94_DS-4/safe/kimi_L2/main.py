import math
import os
from enum import Enum

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TEMPLATES_DIR = 'templates'
FORM_TEMPLATE_FILENAME = 'form.html'
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

PREMIUM_BASE_PRICE = 100
STANDARD_BASE_PRICE = 50
ECONOMY_BASE_PRICE = 20
DEFAULT_BASE_PRICE = 0

BULK_DISCOUNT_RATE = 0.01
BULK_DISCOUNT_CAP = 0.5
SEASONAL_QUANTITY_THRESHOLD = 10
SEASONAL_HIGH_DISCOUNT = 0.2
SEASONAL_LOW_DISCOUNT = 0.1
LOYALTY_DISCOUNT_FACTOR = 0.1

MIN_DISCOUNT = 0
MAX_DISCOUNT = 0.9

QUANTITY_ERROR_MESSAGE = 'Quantity must be positive'
INVALID_DISCOUNT_ERROR_MESSAGE = 'Invalid discount type'
CALCULATION_ERROR_MESSAGE = 'Calculation error'

FORM_TEMPLATE_HTML = """
        <!DOCTYPE html>
        <html>
        <head><title>Dynamic Pricing Calculator</title></head>
        <body>
            <h1>Product Pricing Calculator</h1>
            <form method="post" action="/calculate">
                Product Type:
                <select name="product_type">
                    {% for pt in product_types %}
                    <option value="{{ pt }}">{{ pt|title }}</option>
                    {% endfor %}
                </select><br>
                Quantity: <input type="number" name="quantity" min="1" value="1"><br>
                Discount Type:
                <select name="discount_type">
                    {% for dt in discount_types %}
                    <option value="{{ dt }}">{{ dt|title }}</option>
                    {% endfor %}
                </select><br>
                <button type="submit">Calculate</button>
            </form>
        </body>
        </html>
        """

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)


class ProductType(str, Enum):
    PREMIUM = 'premium'
    STANDARD = 'standard'
    ECONOMY = 'economy'


class DiscountType(str, Enum):
    BULK = 'bulk'
    SEASONAL = 'seasonal'
    LOYALTY = 'loyalty'


# ---------------------------------------------------------------------------
# Discount helpers
# ---------------------------------------------------------------------------
def _bulk_discount(quantity: int) -> float:
    return min(BULK_DISCOUNT_CAP, quantity * BULK_DISCOUNT_RATE)


def _seasonal_discount(quantity: int) -> float:
    if quantity > SEASONAL_QUANTITY_THRESHOLD:
        return SEASONAL_HIGH_DISCOUNT
    return SEASONAL_LOW_DISCOUNT


def _loyalty_discount(quantity: int) -> float:
    return math.log(quantity + 1) * LOYALTY_DISCOUNT_FACTOR


def _clamp_discount(discount: float) -> float:
    return max(MIN_DISCOUNT, min(MAX_DISCOUNT, discount))


class PricingEngine:

    def __init__(self):
        self.base_prices = {
            ProductType.PREMIUM: PREMIUM_BASE_PRICE,
            ProductType.STANDARD: STANDARD_BASE_PRICE,
            ProductType.ECONOMY: ECONOMY_BASE_PRICE,
        }
        self.discount_functions = {
            DiscountType.BULK: _bulk_discount,
            DiscountType.SEASONAL: _seasonal_discount,
            DiscountType.LOYALTY: _loyalty_discount,
        }

    def calculate(self, product_type: ProductType, discount_type: DiscountType, quantity: int):
        try:
            if quantity <= 0:
                raise ValueError(QUANTITY_ERROR_MESSAGE)
            base_price = self.base_prices.get(product_type, DEFAULT_BASE_PRICE)
            discount_func = self.discount_functions.get(discount_type)
            if not discount_func:
                raise ValueError(INVALID_DISCOUNT_ERROR_MESSAGE)
            discount = _clamp_discount(discount_func(quantity))
            return base_price * quantity * (1 - discount)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------
def _build_form_context(request: Request) -> dict:
    return {
        'request': request,
        'product_types': [pt.value for pt in ProductType],
        'discount_types': [dt.value for dt in DiscountType],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get('/', response_class=HTMLResponse)
async def calculator_form(request: Request):
    return templates.TemplateResponse(FORM_TEMPLATE_FILENAME, _build_form_context(request))


@app.post('/calculate')
async def calculate_price(product_type: ProductType=Form(...), discount_type: DiscountType=Form(...), quantity: int=Form(..., gt=0)):
    engine = PricingEngine()
    try:
        total = engine.calculate(product_type, discount_type, quantity)
        return {'product': product_type.value, 'total_price': round(total, 2)}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=CALCULATION_ERROR_MESSAGE)


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------
def _write_form_template() -> None:
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    template_path = os.path.join(TEMPLATES_DIR, FORM_TEMPLATE_FILENAME)
    with open(template_path, 'w') as f:
        f.write(FORM_TEMPLATE_HTML)


def _run_server() -> None:
    import uvicorn
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)


def main() -> None:
    _write_form_template()
    _run_server()


if __name__ == '__main__':
    main()
