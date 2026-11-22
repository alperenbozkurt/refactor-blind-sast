"""Flask application for serving joblib, Keras (HDF5) and ONNX models.

Endpoints:
    POST /upload_model          upload a model file and receive a model id
    POST /predict               run a prediction with a previously uploaded model
    GET  /prediction/<id>       fetch a previously computed prediction
    GET  /models                list the ids of all loaded models
"""

import hashlib
import json
import os
from dataclasses import dataclass

import h5py
import joblib
import numpy as np
import onnxruntime
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Configuration and named constants
# ---------------------------------------------------------------------------

JOBLIB_EXTENSION = '.joblib'
KERAS_EXTENSION = '.h5'
ONNX_EXTENSION = '.onnx'

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

ERR_NO_MODEL_FILE = 'No model file provided'
ERR_NO_SELECTED_FILE = 'No selected file'
ERR_FILE_TYPE_NOT_ALLOWED = 'File type not allowed'
ERR_MODEL_UPLOAD_FAILED = 'Model upload failed'
ERR_INVALID_REQUEST = 'Invalid request'
ERR_PREDICTION_FAILED = 'Prediction failed'
ERR_PREDICTION_NOT_FOUND = 'Prediction not found'
ERR_UNSUPPORTED_MODEL_FORMAT = 'Unsupported model format'
ERR_UNSUPPORTED_MODEL_TYPE = 'Unsupported model type'

LOG_MODEL_LOADING_FAILED = 'Model loading failed: {}'
LOG_PREDICTION_FAILED = 'Prediction failed: {}'

REQUEST_MODEL_FIELD = 'model'


@dataclass(frozen=True)
class ServerConfig:
    """Runtime configuration for the model server."""

    upload_folder: str = './models'
    allowed_extensions: frozenset = frozenset({'joblib', 'h5', 'onnx'})
    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False


CONFIG = ServerConfig()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = CONFIG.upload_folder
app.config['ALLOWED_EXTENSIONS'] = set(CONFIG.allowed_extensions)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def _error_response(message, status):
    return jsonify({'error': message}), status


def _read_file_bytes(path):
    with open(path, 'rb') as file_handle:
        return file_handle.read()


def _load_joblib_model(model_path):
    return joblib.load(model_path)


def _load_keras_model(model_path):
    import tensorflow as tf
    model = tf.keras.models.load_model(model_path)
    model.predict = lambda x: model.predict(np.array(x)).tolist()
    return model


def _load_onnx_model(model_path):
    return onnxruntime.InferenceSession(model_path)


# Loaders keyed by file suffix; tried in order.
_MODEL_LOADERS = (
    (JOBLIB_EXTENSION, _load_joblib_model),
    (KERAS_EXTENSION, _load_keras_model),
    (ONNX_EXTENSION, _load_onnx_model),
)


def _load_model_by_extension(model_path):
    for extension, loader in _MODEL_LOADERS:
        if model_path.endswith(extension):
            return loader(model_path)
    raise ValueError(ERR_UNSUPPORTED_MODEL_FORMAT)


def _run_model_prediction(model, input_data):
    if hasattr(model, 'predict'):
        return model.predict(input_data)
    if isinstance(model, onnxruntime.InferenceSession):
        input_name = model.get_inputs()[0].name
        return model.run(None, {input_name: np.array(input_data)})[0]
    raise ValueError(ERR_UNSUPPORTED_MODEL_TYPE)


def _as_json_serializable(prediction):
    if isinstance(prediction, np.ndarray):
        return prediction.tolist()
    return prediction


def _prediction_id_for(prediction):
    return hashlib.md5(str(prediction).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Model server
# ---------------------------------------------------------------------------

class ModelServer:
    """Registry of loaded models and a cache of computed predictions."""

    def __init__(self):
        self.loaded_models = {}
        self.predictions = {}

    def _generate_model_id(self, model_bytes):
        return hashlib.sha256(model_bytes).hexdigest()

    def load_model(self, model_path):
        try:
            model_id = self._generate_model_id(_read_file_bytes(model_path))
            model = _load_model_by_extension(model_path)
            self.loaded_models[model_id] = model
            return model_id
        except Exception as e:
            print(LOG_MODEL_LOADING_FAILED.format(e))
            return None

    def predict(self, model_id, input_data):
        if model_id not in self.loaded_models:
            return None
        try:
            model = self.loaded_models[model_id]
            if isinstance(input_data, list):
                input_data = np.array(input_data)
            prediction = _run_model_prediction(model, input_data)
            prediction = _as_json_serializable(prediction)
            prediction_id = _prediction_id_for(prediction)
            self.predictions[prediction_id] = prediction
            return prediction_id
        except Exception as e:
            print(LOG_PREDICTION_FAILED.format(e))
            return None


model_server = ModelServer()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/upload_model', methods=['POST'])
def upload_model():
    if REQUEST_MODEL_FIELD not in request.files:
        return _error_response(ERR_NO_MODEL_FILE, HTTP_BAD_REQUEST)
    model_file = request.files[REQUEST_MODEL_FIELD]
    if model_file.filename == '':
        return _error_response(ERR_NO_SELECTED_FILE, HTTP_BAD_REQUEST)
    if not allowed_file(model_file.filename):
        return _error_response(ERR_FILE_TYPE_NOT_ALLOWED, HTTP_BAD_REQUEST)
    filename = secure_filename(model_file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    model_file.save(filepath)
    model_id = model_server.load_model(filepath)
    if model_id:
        return jsonify({'model_id': model_id}), HTTP_OK
    return _error_response(ERR_MODEL_UPLOAD_FAILED, HTTP_BAD_REQUEST)


@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()
    if not data or 'model_id' not in data or 'input_data' not in data:
        return _error_response(ERR_INVALID_REQUEST, HTTP_BAD_REQUEST)
    prediction_id = model_server.predict(data['model_id'], data['input_data'])
    if prediction_id:
        return jsonify({'prediction_id': prediction_id}), HTTP_OK
    return _error_response(ERR_PREDICTION_FAILED, HTTP_BAD_REQUEST)


@app.route('/prediction/<prediction_id>', methods=['GET'])
def get_prediction(prediction_id):
    if prediction_id in model_server.predictions:
        return jsonify({'prediction': model_server.predictions[prediction_id]}), HTTP_OK
    return _error_response(ERR_PREDICTION_NOT_FOUND, HTTP_NOT_FOUND)


@app.route('/models', methods=['GET'])
def list_models():
    return jsonify({'models': list(model_server.loaded_models.keys())}), HTTP_OK


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app.run(host=CONFIG.host, port=CONFIG.port, debug=CONFIG.debug)


if __name__ == '__main__':
    main()
