"""Flask application exposing pickled machine-learning models over HTTP."""

import hashlib
import json
import os
import pickle

import numpy as np
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename


class ServerConfig:
    """Static configuration for the model server."""

    UPLOAD_FOLDER = './models'
    HOST = '0.0.0.0'
    PORT = 5000
    DEBUG = False


MODEL_FILE_FIELD = 'model'

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

ERR_NO_MODEL_FILE = 'No model file provided'
ERR_NO_SELECTED_FILE = 'No selected file'
ERR_MODEL_UPLOAD_FAILED = 'Model upload failed'
ERR_INVALID_REQUEST = 'Invalid request'
ERR_PREDICTION_FAILED = 'Prediction failed'
ERR_PREDICTION_NOT_FOUND = 'Prediction not found'


def create_app():
    """Create and configure the Flask application instance."""
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = ServerConfig.UPLOAD_FOLDER
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    return app


def _error_response(message, status_code):
    """Build a JSON error body paired with an HTTP status code."""
    return (jsonify({'error': message}), status_code)


app = create_app()


class ModelServer:
    """In-memory registry of loaded models and their cached predictions."""

    def __init__(self):
        self.loaded_models = {}
        self.predictions = {}

    def _generate_model_id(self, model_bytes):
        return hashlib.sha256(model_bytes).hexdigest()

    def _generate_prediction_id(self, prediction):
        return hashlib.md5(str(prediction).encode()).hexdigest()

    @staticmethod
    def _read_model_bytes(model_path):
        with open(model_path, 'rb') as f:
            return f.read()

    @staticmethod
    def _to_model_input(input_data):
        if isinstance(input_data, list):
            return np.array(input_data)
        return input_data

    def load_model(self, model_path):
        try:
            model_bytes = self._read_model_bytes(model_path)
            model = pickle.loads(model_bytes)
            model_id = self._generate_model_id(model_bytes)
            self.loaded_models[model_id] = model
            return model_id
        except Exception as e:
            print(f'Model loading failed: {e}')
            return None

    def predict(self, model_id, input_data):
        if model_id not in self.loaded_models:
            return None
        try:
            model = self.loaded_models[model_id]
            prediction = model.predict(self._to_model_input(input_data))
            prediction_id = self._generate_prediction_id(prediction)
            self.predictions[prediction_id] = prediction.tolist()
            return prediction_id
        except Exception as e:
            print(f'Prediction failed: {e}')
            return None


model_server = ModelServer()


def _save_model_file(model_file):
    """Persist an uploaded model file and return its path on disk."""
    filename = secure_filename(model_file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    model_file.save(filepath)
    return filepath


@app.route('/upload_model', methods=['POST'])
def upload_model():
    if MODEL_FILE_FIELD not in request.files:
        return _error_response(ERR_NO_MODEL_FILE, HTTP_BAD_REQUEST)
    model_file = request.files[MODEL_FILE_FIELD]
    if model_file.filename == '':
        return _error_response(ERR_NO_SELECTED_FILE, HTTP_BAD_REQUEST)
    model_id = model_server.load_model(_save_model_file(model_file))
    if model_id:
        return (jsonify({'model_id': model_id}), HTTP_OK)
    return _error_response(ERR_MODEL_UPLOAD_FAILED, HTTP_BAD_REQUEST)


@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()
    if not data or 'model_id' not in data or 'input_data' not in data:
        return _error_response(ERR_INVALID_REQUEST, HTTP_BAD_REQUEST)
    prediction_id = model_server.predict(data['model_id'], data['input_data'])
    if prediction_id:
        return (jsonify({'prediction_id': prediction_id}), HTTP_OK)
    return _error_response(ERR_PREDICTION_FAILED, HTTP_BAD_REQUEST)


@app.route('/prediction/<prediction_id>', methods=['GET'])
def get_prediction(prediction_id):
    if prediction_id in model_server.predictions:
        return (jsonify({'prediction': model_server.predictions[prediction_id]}), HTTP_OK)
    return _error_response(ERR_PREDICTION_NOT_FOUND, HTTP_NOT_FOUND)


@app.route('/models', methods=['GET'])
def list_models():
    return (jsonify({'models': list(model_server.loaded_models.keys())}), HTTP_OK)


def main():
    app.run(host=ServerConfig.HOST, port=ServerConfig.PORT, debug=ServerConfig.DEBUG)


if __name__ == '__main__':
    main()
