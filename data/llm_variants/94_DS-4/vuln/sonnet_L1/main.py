import math
import os

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = 'templates'
FORM_TEMPLATE_NAME = 'form.html'
FORM_TEMPLATE_PATH = f'{TEMPLATES_DIR}/{FORM_TEMPLATE_NAME}'
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

FORM_HTML = """
        <!DOCTYPE html>
        <html>
        <head><title>Dynamic Pricing Calculator</title></head>
        <body>
            <h1>Product Pricing Calculator</h1>
            <form method="post" action="/calculate">
                Product Type: 
                <select name="product_type">
                    <option value="premium">Premium</option>
                    <option value="standard">Standard</option>
                    <option value="economy">Economy</option>
                </select><br>
                Quantity: <input type="number" name="quantity" min="1" value="1"><br>
                Discount Logic (Python): 
                <input type="text" name="discount_logic" 
                       placeholder="e.g., math.log(quantity)*0.1" size="40"><br>
                <button type="submit">Calculate</button>
            </form>
        </body>
        </html>
        """

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)


class PricingEngine:
    """Calculates the total price for a product using a discount expression."""

    def __init__(self):
        self.base_prices = {'premium': 100, 'standard': 50, 'economy': 20}

    def _evaluate_discount(self, discount_logic: str, quantity: int):
        # NOTE: the discount expression is evaluated with eval(), exactly as
        # in the original implementation (behaviour intentionally preserved).
        return eval(discount_logic, {'math': math, 'quantity': quantity})

    def calculate(self, product_type: str, discount_logic: str, quantity: int):
        try:
            base_price = self.base_prices.get(product_type, 0)
            discount = self._evaluate_discount(discount_logic, quantity)
            return base_price * quantity * (1 - discount)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@app.get('/', response_class=HTMLResponse)
async def calculator_form(request: Request):
    return templates.TemplateResponse(FORM_TEMPLATE_NAME, {'request': request})


@app.post('/calculate')
async def calculate_price(
    product_type: str = Form(...),
    discount_logic: str = Form(...),
    quantity: int = Form(...),
):
    engine = PricingEngine()
    try:
        total = engine.calculate(product_type, discount_logic, quantity)
        return {'product': product_type, 'total_price': total}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail='Calculation error')


def write_form_template():
    """Create the templates directory and write the HTML form template."""
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    with open(FORM_TEMPLATE_PATH, 'w') as f:
        f.write(FORM_HTML)


if __name__ == '__main__':
    import uvicorn

    write_form_template()
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
