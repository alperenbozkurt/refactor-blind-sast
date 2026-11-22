"""Dynamic pricing calculator web application.

A small FastAPI app that renders a pricing form and calculates
discounted totals based on product type, discount type and quantity.
"""

import math
import os
from enum import Enum

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

FORM_HTML = """
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


class ProductType(str, Enum):
    PREMIUM = "premium"
    STANDARD = "standard"
    ECONOMY = "economy"


class DiscountType(str, Enum):
    BULK = "bulk"
    SEASONAL = "seasonal"
    LOYALTY = "loyalty"


class PricingEngine:
    """Compute discounted totals from base prices and discount rules."""

    MIN_DISCOUNT = 0
    MAX_DISCOUNT = 0.9

    def __init__(self):
        self.base_prices = {
            ProductType.PREMIUM: 100,
            ProductType.STANDARD: 50,
            ProductType.ECONOMY: 20,
        }
        self.discount_functions = {
            DiscountType.BULK: self._bulk_discount,
            DiscountType.SEASONAL: self._seasonal_discount,
            DiscountType.LOYALTY: self._loyalty_discount,
        }

    @staticmethod
    def _bulk_discount(quantity):
        return min(0.5, quantity * 0.01)

    @staticmethod
    def _seasonal_discount(quantity):
        return 0.2 if quantity > 10 else 0.1

    @staticmethod
    def _loyalty_discount(quantity):
        return math.log(quantity + 1) * 0.1

    def calculate(self, product_type: ProductType, discount_type: DiscountType, quantity: int):
        """Return the discounted total for the given inputs."""
        try:
            if quantity <= 0:
                raise ValueError("Quantity must be positive")
            base_price = self.base_prices.get(product_type, 0)
            discount_func = self.discount_functions.get(discount_type)
            if not discount_func:
                raise ValueError("Invalid discount type")
            raw_discount = discount_func(quantity)
            discount = max(self.MIN_DISCOUNT, min(self.MAX_DISCOUNT, raw_discount))
            return base_price * quantity * (1 - discount)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def calculator_form(request: Request):
    """Render the pricing calculator form."""
    context = {
        "request": request,
        "product_types": [product_type.value for product_type in ProductType],
        "discount_types": [discount_type.value for discount_type in DiscountType],
    }
    return templates.TemplateResponse("form.html", context)


@app.post("/calculate")
async def calculate_price(
    product_type: ProductType = Form(...),
    discount_type: DiscountType = Form(...),
    quantity: int = Form(..., gt=0),
):
    """Calculate the total price for the submitted form values."""
    engine = PricingEngine()
    try:
        total = engine.calculate(product_type, discount_type, quantity)
        return {"product": product_type.value, "total_price": round(total, 2)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Calculation error")


def _write_form_template():
    """Write the default form template into the templates directory."""
    os.makedirs("templates", exist_ok=True)
    with open("templates/form.html", "w") as f:
        f.write(FORM_HTML)


if __name__ == "__main__":
    import uvicorn

    _write_form_template()
    uvicorn.run(app, host="0.0.0.0", port=8000)
