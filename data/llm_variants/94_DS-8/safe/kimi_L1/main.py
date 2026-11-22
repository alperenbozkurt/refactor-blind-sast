import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from quart import Quart, jsonify, request

app = Quart(__name__)


class TemplateType(str, Enum):
    """Supported response template types."""

    USER = "user"
    PRODUCT = "product"


@dataclass
class TemplateVariables:
    """Variables used when rendering a response template."""

    user_id: int = 0
    product_id: str = ""


class ResponseProcessor:
    """Builds API responses from named templates and JSON variables."""

    def __init__(self):
        self.response_templates = {
            TemplateType.USER: lambda variables: {
                "id": variables.user_id,
                "name": "Test User",
            },
            TemplateType.PRODUCT: lambda variables: {
                "sku": variables.product_id,
                "price": 19.99,
            },
        }

    async def process_response(
        self, template_type: TemplateType, variables_json: str
    ) -> Dict[str, Any]:
        try:
            variables_dict = json.loads(variables_json)
            template_variables = TemplateVariables(
                user_id=int(variables_dict.get("user_id", 0)),
                product_id=str(variables_dict.get("product_id", "")),
            )
            template = self.response_templates.get(template_type)
            if not template:
                return {"error": "Invalid template type"}
            return template(template_variables)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON: {e}"}
        except ValueError as e:
            return {"error": f"Invalid value: {e}"}
        except Exception as e:
            return {"error": f"Processing failed: {e}"}


processor = ResponseProcessor()


@app.route("/", methods=["GET"])
async def index():
    return """
    <form action="/api" method="post">
        <h2>API Response Generator</h2>
        Template Type:
        <select name="template_type">
            <option value="user">User</option>
            <option value="product">Product</option>
        </select><br>
        Variables (JSON):<br>
        <textarea name="variables_json" rows=6 cols=50>
{
    "user_id": 42,
    "product_id": "XJ-209"
}
        </textarea><br>
        <button type="submit">Generate Response</button>
    </form>
    """


@app.route("/api", methods=["POST"])
async def api_handler():
    form = await request.form
    try:
        template_type = TemplateType(form["template_type"])
        result = await processor.process_response(
            template_type, form["variables_json"]
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": f"Invalid template type: {e}"})


@app.route("/debug", methods=["GET"])
async def debug():
    return jsonify(
        {
            "status": "active",
            "endpoints": [str(rule) for rule in app.url_map.iter_rules()],
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
