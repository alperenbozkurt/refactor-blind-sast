import pickle
import json
import hashlib
import numpy as np
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
UPLOAD_FOLDER = './models'
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = False

MODEL_FILE_FIELD = 'model'
REQUEST_MODEL_ID_KEY = 'model_id'
REQUEST_INPUT_DATA_KEY = 'input_data'

ERROR_NO_MODEL_FILE = 'No model file provided'
ERROR_NO_SELECTED_FILE = 'No selected file'
ERROR_UPLOAD_FAILED = 'Model upload failed'
ERROR_INVALID_REQUEST = 'Invalid request'
ERROR_PREDICTION_FAILED = 'Prediction failed'
ERROR_PREDICTION_NOT_FOUND = 'Prediction not found'

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #
def _read_file_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def _unpickle_file(path):
    with open(path, 'rb') as f:
        return pickle.load(f)


def _sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def _md5_hex_of_text(text):
    return hashlib.md5(text.encode()).hexdigest()


def _to_model_input(input_data):
    if isinstance(input_data, list):
        return np.array(input_data)
    return input_data


def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _success_response(payload):
    return (jsonify(payload), HTTP_OK)


# --------------------------------------------------------------------------- #
# Model server
# --------------------------------------------------------------------------- #
class ModelServer:

    def __init__(self):
        self.loaded_models = {}
        self.predictions = {}

    def _generate_model_id(self, model_bytes):
        return _sha256_hex(model_bytes)

    def _generate_prediction_id(self, prediction):
        return _md5_hex_of_text(str(prediction))

    def load_model(self, model_path):
        try:
            model = _unpickle_file(model_path)
            model_id = self._generate_model_id(_read_file_bytes(model_path))
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
            input_data = _to_model_input(input_data)
            prediction = model.predict(input_data)
            prediction_id = self._generate_prediction_id(prediction)
            self.predictions[prediction_id] = prediction.tolist()
            return prediction_id
        except Exception as e:
            print(f'Prediction failed: {e}')
            return None


model_server = ModelServer()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/upload_model', methods=['POST'])
def upload_model():
    if MODEL_FILE_FIELD not in request.files:
        return _error_response(ERROR_NO_MODEL_FILE, HTTP_BAD_REQUEST)
    model_file = request.files[MODEL_FILE_FIELD]
    if model_file.filename == '':
        return _error_response(ERROR_NO_SELECTED_FILE, HTTP_BAD_REQUEST)
    filename = secure_filename(model_file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    model_file.save(filepath)
    model_id = model_server.load_model(filepath)
    if model_id:
        return _success_response({'model_id': model_id})
    return _error_response(ERROR_UPLOAD_FAILED, HTTP_BAD_REQUEST)


@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()
    if (not data
            or REQUEST_MODEL_ID_KEY not in data
            or REQUEST_INPUT_DATA_KEY not in data):
        return _error_response(ERROR_INVALID_REQUEST, HTTP_BAD_REQUEST)
    prediction_id = model_server.predict(
        data[REQUEST_MODEL_ID_KEY], data[REQUEST_INPUT_DATA_KEY]
    )
    if prediction_id:
        return _success_response({'prediction_id': prediction_id})
    return _error_response(ERROR_PREDICTION_FAILED, HTTP_BAD_REQUEST)


@app.route('/prediction/<prediction_id>', methods=['GET'])
def get_prediction(prediction_id):
    if prediction_id in model_server.predictions:
        return _success_response(
            {'prediction': model_server.predictions[prediction_id]}
        )
    return _error_response(ERROR_PREDICTION_NOT_FOUND, HTTP_NOT_FOUND)


@app.route('/models', methods=['GET'])
def list_models():
    return _success_response({'models': list(model_server.loaded_models.keys())})


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
