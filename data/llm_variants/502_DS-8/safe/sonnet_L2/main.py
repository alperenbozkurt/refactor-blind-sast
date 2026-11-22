import json
import hashlib
import numpy as np
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import joblib
import h5py
import onnxruntime

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
UPLOAD_FOLDER = './models'
ALLOWED_EXTENSIONS = {'joblib', 'h5', 'onnx'}

HOST = '0.0.0.0'
PORT = 5000
DEBUG = False

MODEL_FILE_FIELD = 'model'
REQUEST_MODEL_ID_FIELD = 'model_id'
REQUEST_INPUT_DATA_FIELD = 'input_data'

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

# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# --------------------------------------------------------------------------- #
# Model loading helpers
# --------------------------------------------------------------------------- #
def _read_file_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def _load_joblib_model(model_path):
    return joblib.load(model_path)


def _load_h5_model(model_path):
    import tensorflow as tf
    model = tf.keras.models.load_model(model_path)
    model.predict = lambda x: model.predict(np.array(x)).tolist()
    return model


def _load_onnx_model(model_path):
    return onnxruntime.InferenceSession(model_path)


# Ordered (extension suffix, loader) pairs.
_MODEL_LOADERS = (
    ('.joblib', _load_joblib_model),
    ('.h5', _load_h5_model),
    ('.onnx', _load_onnx_model),
)


def _load_model_by_extension(model_path):
    for suffix, loader in _MODEL_LOADERS:
        if model_path.endswith(suffix):
            return loader(model_path)
    raise ValueError('Unsupported model format')


# --------------------------------------------------------------------------- #
# Prediction helpers
# --------------------------------------------------------------------------- #
def _run_model(model, input_data):
    if hasattr(model, 'predict'):
        return model.predict(input_data)
    if isinstance(model, onnxruntime.InferenceSession):
        input_name = model.get_inputs()[0].name
        return model.run(None, {input_name: np.array(input_data)})[0]
    raise ValueError('Unsupported model type')


def _normalize_prediction(prediction):
    if isinstance(prediction, np.ndarray):
        return prediction.tolist()
    return prediction


def _generate_prediction_id(prediction):
    return hashlib.md5(str(prediction).encode()).hexdigest()


# --------------------------------------------------------------------------- #
# Model server
# --------------------------------------------------------------------------- #
class ModelServer:

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
            print(f'Model loading failed: {e}')
            return None

    def predict(self, model_id, input_data):
        if model_id not in self.loaded_models:
            return None
        try:
            model = self.loaded_models[model_id]
            if isinstance(input_data, list):
                input_data = np.array(input_data)
            prediction = _normalize_prediction(_run_model(model, input_data))
            prediction_id = _generate_prediction_id(prediction)
            self.predictions[prediction_id] = prediction
            return prediction_id
        except Exception as e:
            print(f'Prediction failed: {e}')
            return None


model_server = ModelServer()


# --------------------------------------------------------------------------- #
# Response helpers
# --------------------------------------------------------------------------- #
def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _ok_response(payload):
    return (jsonify(payload), HTTP_OK)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/upload_model', methods=['POST'])
def upload_model():
    if MODEL_FILE_FIELD not in request.files:
        return _error_response(ERR_NO_MODEL_FILE, HTTP_BAD_REQUEST)
    model_file = request.files[MODEL_FILE_FIELD]
    if model_file.filename == '':
        return _error_response(ERR_NO_SELECTED_FILE, HTTP_BAD_REQUEST)
    if not allowed_file(model_file.filename):
        return _error_response(ERR_FILE_TYPE_NOT_ALLOWED, HTTP_BAD_REQUEST)
    filename = secure_filename(model_file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    model_file.save(filepath)
    model_id = model_server.load_model(filepath)
    if model_id:
        return _ok_response({'model_id': model_id})
    return _error_response(ERR_MODEL_UPLOAD_FAILED, HTTP_BAD_REQUEST)


@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()
    if (not data
            or REQUEST_MODEL_ID_FIELD not in data
            or REQUEST_INPUT_DATA_FIELD not in data):
        return _error_response(ERR_INVALID_REQUEST, HTTP_BAD_REQUEST)
    prediction_id = model_server.predict(
        data[REQUEST_MODEL_ID_FIELD], data[REQUEST_INPUT_DATA_FIELD]
    )
    if prediction_id:
        return _ok_response({'prediction_id': prediction_id})
    return _error_response(ERR_PREDICTION_FAILED, HTTP_BAD_REQUEST)


@app.route('/prediction/<prediction_id>', methods=['GET'])
def get_prediction(prediction_id):
    if prediction_id in model_server.predictions:
        return _ok_response({'prediction': model_server.predictions[prediction_id]})
    return _error_response(ERR_PREDICTION_NOT_FOUND, HTTP_NOT_FOUND)


@app.route('/models', methods=['GET'])
def list_models():
    return _ok_response({'models': list(model_server.loaded_models.keys())})


if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=DEBUG)
