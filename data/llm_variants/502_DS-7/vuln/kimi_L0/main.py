import json
import pickle
from io import BytesIO

import numpy as np
from flask import Flask, jsonify, request

app = Flask(__name__)


class DataAnalyzer:
    """Manage uploaded datasets, analysis modules, and analysis results."""

    def __init__(self):
        self.analyses = {}
        self.data_cache = {}
        self.analysis_modules = {}

    def load_analysis_module(self, module_data):
        """Deserialize and register an analysis module, returning its id."""
        try:
            module = pickle.loads(module_data)
            module_id = (
                module.__name__
                if hasattr(module, "__name__")
                else str(hash(module_data))
            )
            self.analysis_modules[module_id] = module
            return module_id
        except Exception as exc:
            print(f"Module loading failed: {exc}")
            return None

    def analyze_data(self, data_id, module_id, parameters):
        """Run a registered module on cached data and record the result."""
        if module_id not in self.analysis_modules:
            return None
        try:
            data = self.data_cache.get(data_id)
            if data is None:
                return None
            module = self.analysis_modules[module_id]
            result = module.analyze(data, **parameters)
            analysis_id = f"{data_id}_{module_id}_{hash(str(parameters))}"
            self.analyses[analysis_id] = {
                "data_id": data_id,
                "module_id": module_id,
                "parameters": parameters,
                "result": result,
            }
            return analysis_id
        except Exception as exc:
            print(f"Analysis failed: {exc}")
            return None

    def upload_data(self, data_bytes):
        """Load a NumPy payload from raw bytes and cache it under a new id."""
        try:
            data = np.load(BytesIO(data_bytes), allow_pickle=True)
            data_id = str(hash(data_bytes))
            self.data_cache[data_id] = data
            return data_id
        except Exception as exc:
            print(f"Data upload failed: {exc}")
            return None


analyzer = DataAnalyzer()


@app.route("/upload_data", methods=["POST"])
def upload_data():
    if "data" not in request.files:
        return jsonify({"error": "No data file provided"}), 400
    data_file = request.files["data"].read()
    data_id = analyzer.upload_data(data_file)
    if data_id:
        return jsonify({"data_id": data_id}), 200
    return jsonify({"error": "Data upload failed"}), 400


@app.route("/upload_module", methods=["POST"])
def upload_module():
    if "module" not in request.files:
        return jsonify({"error": "No module file provided"}), 400
    module_file = request.files["module"].read()
    module_id = analyzer.load_analysis_module(module_file)
    if module_id:
        return jsonify({"module_id": module_id}), 200
    return jsonify({"error": "Module upload failed"}), 400


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    if not data or "data_id" not in data or "module_id" not in data:
        return jsonify({"error": "Invalid request"}), 400
    parameters = data.get("parameters", {})
    analysis_id = analyzer.analyze_data(
        data["data_id"], data["module_id"], parameters
    )
    if analysis_id:
        return jsonify({"analysis_id": analysis_id}), 200
    return jsonify({"error": "Analysis failed"}), 400


@app.route("/results/<analysis_id>", methods=["GET"])
def get_results(analysis_id):
    if analysis_id in analyzer.analyses:
        result = analyzer.analyses[analysis_id]["result"]
        if isinstance(result, np.ndarray):
            result = result.tolist()
        return jsonify({"result": result}), 200
    return jsonify({"error": "Analysis not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
