"""Dynamic pricing calculator web application."""

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import math
import os

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

TEMPLATES_DIRECTORY = 'templates'
FORM_TEMPLATE_NAME = 'form.html'
FORM_TEMPLATE_PATH = TEMPLATES_DIRECTORY + '/' + FORM_TEMPLATE_NAME

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500
CALCULATION_ERROR_DETAIL = 'Calculation error'
UNKNOWN_PRODUCT_BASE_PRICE = 0

DEFAULT_BASE_PRICES = {
    'premium': 100,
    'standard': 50,
    'economy': 20,
}

FORM_HTML = '\n        <!DOCTYPE html>\n        <html>\n        <head><title>Dynamic Pricing Calculator</title></head>\n        <body>\n            <h1>Product Pricing Calculator</h1>\n            <form method="post" action="/calculate">\n                Product Type: \n                <select name="product_type">\n                    <option value="premium">Premium</option>\n                    <option value="standard">Standard</option>\n                    <option value="economy">Economy</option>\n                </select><br>\n                Quantity: <input type="number" name="quantity" min="1" value="1"><br>\n                Discount Logic (Python): \n                <input type="text" name="discount_logic" \n                       placeholder="e.g., math.log(quantity)*0.1" size="40"><br>\n                <button type="submit">Calculate</button>\n            </form>\n        </body>\n        </html>\n        '

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIRECTORY)


class PricingEngine:

    def __init__(self):
        self.base_prices = dict(DEFAULT_BASE_PRICES)

    def calculate(self, product_type: str, discount_logic: str, quantity: int):
        try:
            base_price = self._lookup_base_price(product_type)
            discount = self._evaluate_discount(discount_logic, quantity)
            return self._calculate_total(base_price, discount, quantity)
        except Exception as e:
            raise HTTPException(status_code=HTTP_BAD_REQUEST, detail=str(e))

    def _lookup_base_price(self, product_type: str):
        return self.base_prices.get(product_type, UNKNOWN_PRODUCT_BASE_PRICE)

    @staticmethod
    def _evaluate_discount(discount_logic: str, quantity: int):
        return eval(discount_logic, {'math': math, 'quantity': quantity})

    @staticmethod
    def _calculate_total(base_price, discount, quantity: int):
        return base_price * quantity * (1 - discount)


@app.get('/', response_class=HTMLResponse)
async def calculator_form(request: Request):
    return templates.TemplateResponse(FORM_TEMPLATE_NAME, {'request': request})


@app.post('/calculate')
async def calculate_price(product_type: str=Form(...), discount_logic: str=Form(...), quantity: int=Form(...)):
    engine = PricingEngine()
    try:
        total = engine.calculate(product_type, discount_logic, quantity)
        return {'product': product_type, 'total_price': total}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=HTTP_INTERNAL_SERVER_ERROR, detail=CALCULATION_ERROR_DETAIL)


# ---------------------------------------------------------------------------
# Command-line entry point helpers
# ---------------------------------------------------------------------------

def _ensure_templates_directory() -> None:
    os.makedirs(TEMPLATES_DIRECTORY, exist_ok=True)


def _write_form_template() -> None:
    with open(FORM_TEMPLATE_PATH, 'w') as f:
        f.write(FORM_HTML)


def _run_server() -> None:
    import uvicorn
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)


def main() -> None:
    _ensure_templates_directory()
    _write_form_template()
    _run_server()


if __name__ == '__main__':
    main()
