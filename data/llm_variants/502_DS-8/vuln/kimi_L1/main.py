"""Flask application for uploading pickled models and serving predictions."""

import hashlib
import json
import os
import pickle

import numpy as np
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './models'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


class ModelServer:
    """In-memory registry of loaded models and their prediction results."""

    def __init__(self):
        self.loaded_models = {}
        self.predictions = {}

    def _generate_model_id(self, model_bytes):
        return hashlib.sha256(model_bytes).hexdigest()

    def load_model(self, model_path):
        """Unpickle a model from disk and register it under its content hash."""
        try:
            with open(model_path, 'rb') as f:
                model = pickle.load(f)
            with open(model_path, 'rb') as f:
                model_id = self._generate_model_id(f.read())
            self.loaded_models[model_id] = model
            return model_id
        except Exception as e:
            print(f'Model loading failed: {e}')
            return None

    def predict(self, model_id, input_data):
        """Run a prediction and store the result under a generated id."""
        if model_id not in self.loaded_models:
            return None
        try:
            model = self.loaded_models[model_id]
            if isinstance(input_data, list):
                input_data = np.array(input_data)
            prediction = model.predict(input_data)
            prediction_id = hashlib.md5(str(prediction).encode()).hexdigest()
            self.predictions[prediction_id] = prediction.tolist()
            return prediction_id
        except Exception as e:
            print(f'Prediction failed: {e}')
            return None


model_server = ModelServer()


@app.route('/upload_model', methods=['POST'])
def upload_model():
    """Save an uploaded model file and load it into the server."""
    if 'model' not in request.files:
        return jsonify({'error': 'No model file provided'}), 400

    model_file = request.files['model']
    if model_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = secure_filename(model_file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    model_file.save(filepath)

    model_id = model_server.load_model(filepath)
    if model_id:
        return jsonify({'model_id': model_id}), 200
    return jsonify({'error': 'Model upload failed'}), 400


@app.route('/predict', methods=['POST'])
def predict():
    """Run a prediction with a previously uploaded model."""
    data = request.get_json()
    if not data or 'model_id' not in data or 'input_data' not in data:
        return jsonify({'error': 'Invalid request'}), 400

    prediction_id = model_server.predict(data['model_id'], data['input_data'])
    if prediction_id:
        return jsonify({'prediction_id': prediction_id}), 200
    return jsonify({'error': 'Prediction failed'}), 400


@app.route('/prediction/<prediction_id>', methods=['GET'])
def get_prediction(prediction_id):
    """Retrieve a stored prediction by its id."""
    if prediction_id in model_server.predictions:
        return jsonify({'prediction': model_server.predictions[prediction_id]}), 200
    return jsonify({'error': 'Prediction not found'}), 404


@app.route('/models', methods=['GET'])
def list_models():
    """List the ids of all currently loaded models."""
    return jsonify({'models': list(model_server.loaded_models.keys())}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
