"""Dynamic product pricing calculator web application."""

import math
import os
from enum import Enum

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = "templates"
FORM_TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, "form.html")
FORM_TEMPLATE = (
    "\n"
    "        <!DOCTYPE html>\n"
    "        <html>\n"
    "        <head><title>Dynamic Pricing Calculator</title></head>\n"
    "        <body>\n"
    "            <h1>Product Pricing Calculator</h1>\n"
    '            <form method="post" action="/calculate">\n'
    "                Product Type: \n"
    '                <select name="product_type">\n'
    "                    {% for pt in product_types %}\n"
    '                    <option value="{{ pt }}">{{ pt|title }}</option>\n'
    "                    {% endfor %}\n"
    "                </select><br>\n"
    '                Quantity: <input type="number" name="quantity" min="1" value="1"><br>\n'
    "                Discount Type:\n"
    '                <select name="discount_type">\n'
    "                    {% for dt in discount_types %}\n"
    '                    <option value="{{ dt }}">{{ dt|title }}</option>\n'
    "                    {% endfor %}\n"
    "                </select><br>\n"
    '                <button type="submit">Calculate</button>\n'
    "            </form>\n"
    "        </body>\n"
    "        </html>\n"
    "        "
)

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)


class ProductType(str, Enum):
    PREMIUM = "premium"
    STANDARD = "standard"
    ECONOMY = "economy"


class DiscountType(str, Enum):
    BULK = "bulk"
    SEASONAL = "seasonal"
    LOYALTY = "loyalty"


class PricingEngine:
    """Compute product prices with quantity-dependent discounts."""

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
    def _bulk_discount(quantity: int) -> float:
        return min(0.5, quantity * 0.01)

    @staticmethod
    def _seasonal_discount(quantity: int) -> float:
        return 0.2 if quantity > 10 else 0.1

    @staticmethod
    def _loyalty_discount(quantity: int) -> float:
        return math.log(quantity + 1) * 0.1

    def calculate(self, product_type: ProductType, discount_type: DiscountType, quantity: int):
        try:
            if quantity <= 0:
                raise ValueError("Quantity must be positive")
            base_price = self.base_prices.get(product_type, 0)
            discount_func = self.discount_functions.get(discount_type)
            if not discount_func:
                raise ValueError("Invalid discount type")
            discount = discount_func(quantity)
            discount = max(self.MIN_DISCOUNT, min(self.MAX_DISCOUNT, discount))
            return base_price * quantity * (1 - discount)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def calculator_form(request: Request):
    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "product_types": [pt.value for pt in ProductType],
            "discount_types": [dt.value for dt in DiscountType],
        },
    )


@app.post("/calculate")
async def calculate_price(
    product_type: ProductType = Form(...),
    discount_type: DiscountType = Form(...),
    quantity: int = Form(..., gt=0),
):
    engine = PricingEngine()
    try:
        total = engine.calculate(product_type, discount_type, quantity)
        return {"product": product_type.value, "total_price": round(total, 2)}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Calculation error")


if __name__ == "__main__":
    import uvicorn

    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    with open(FORM_TEMPLATE_PATH, "w") as f:
        f.write(FORM_TEMPLATE)
    uvicorn.run(app, host="0.0.0.0", port=8000)
