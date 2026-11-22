from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import math
import os

app = FastAPI()
templates = Jinja2Templates(directory='templates')

FORM_TEMPLATE_HTML = (
    '\n        <!DOCTYPE html>\n        <html>\n        <head><title>Dynamic Pricing Calculator</title></head>\n'
    '        <body>\n            <h1>Product Pricing Calculator</h1>\n'
    '            <form method="post" action="/calculate">\n                Product Type: \n'
    '                <select name="product_type">\n'
    '                    <option value="premium">Premium</option>\n'
    '                    <option value="standard">Standard</option>\n'
    '                    <option value="economy">Economy</option>\n'
    '                </select><br>\n'
    '                Quantity: <input type="number" name="quantity" min="1" value="1"><br>\n'
    '                Discount Logic (Python): \n'
    '                <input type="text" name="discount_logic" \n'
    '                       placeholder="e.g., math.log(quantity)*0.1" size="40"><br>\n'
    '                <button type="submit">Calculate</button>\n'
    '            </form>\n        </body>\n        </html>\n        '
)


class PricingEngine:

    def __init__(self):
        self.base_prices = {'premium': 100, 'standard': 50, 'economy': 20}

    def calculate(self, product_type: str, discount_logic: str, quantity: int):
        try:
            base_price = self.base_prices.get(product_type, 0)
            # NOTE: eval on user-supplied input is unsafe (arbitrary code execution);
            # retained here only to preserve the original behaviour exactly.
            discount = eval(discount_logic, {'math': math, 'quantity': quantity})
            return base_price * quantity * (1 - discount)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@app.get('/', response_class=HTMLResponse)
async def calculator_form(request: Request):
    return templates.TemplateResponse('form.html', {'request': request})


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


def _write_form_template():
    os.makedirs('templates', exist_ok=True)
    with open('templates/form.html', 'w') as f:
        f.write(FORM_TEMPLATE_HTML)


if __name__ == '__main__':
    import uvicorn

    _write_form_template()
    uvicorn.run(app, host='0.0.0.0', port=8000)
