import json
import hashlib
import numpy as np
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import joblib
import h5py
import onnxruntime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './models'
app.config['ALLOWED_EXTENSIONS'] = {'joblib', 'h5', 'onnx'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    return ('.' in filename
            and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS'])


def _load_joblib_model(model_path):
    return joblib.load(model_path)


def _load_h5_model(model_path):
    import tensorflow as tf
    model = tf.keras.models.load_model(model_path)
    model.predict = lambda x: model.predict(np.array(x)).tolist()
    return model


def _load_onnx_model(model_path):
    return onnxruntime.InferenceSession(model_path)


_MODEL_LOADERS = (
    ('.joblib', _load_joblib_model),
    ('.h5', _load_h5_model),
    ('.onnx', _load_onnx_model),
)


class ModelServer:

    def __init__(self):
        self.loaded_models = {}
        self.predictions = {}

    def _generate_model_id(self, model_bytes):
        return hashlib.sha256(model_bytes).hexdigest()

    def _read_bytes(self, path):
        with open(path, 'rb') as f:
            return f.read()

    def _load_by_extension(self, model_path):
        for suffix, loader in _MODEL_LOADERS:
            if model_path.endswith(suffix):
                return loader(model_path)
        raise ValueError('Unsupported model format')

    def load_model(self, model_path):
        try:
            model_id = self._generate_model_id(self._read_bytes(model_path))
            model = self._load_by_extension(model_path)
            self.loaded_models[model_id] = model
            return model_id
        except Exception as e:
            print(f'Model loading failed: {e}')
            return None

    def _run_model(self, model, input_data):
        if hasattr(model, 'predict'):
            return model.predict(input_data)
        if isinstance(model, onnxruntime.InferenceSession):
            input_name = model.get_inputs()[0].name
            return model.run(None, {input_name: np.array(input_data)})[0]
        raise ValueError('Unsupported model type')

    def predict(self, model_id, input_data):
        if model_id not in self.loaded_models:
            return None
        try:
            model = self.loaded_models[model_id]
            if isinstance(input_data, list):
                input_data = np.array(input_data)
            prediction = self._run_model(model, input_data)
            if isinstance(prediction, np.ndarray):
                prediction = prediction.tolist()
            prediction_id = hashlib.md5(str(prediction).encode()).hexdigest()
            self.predictions[prediction_id] = prediction
            return prediction_id
        except Exception as e:
            print(f'Prediction failed: {e}')
            return None


model_server = ModelServer()


def _error(message, status):
    return (jsonify({'error': message}), status)


@app.route('/upload_model', methods=['POST'])
def upload_model():
    if 'model' not in request.files:
        return _error('No model file provided', 400)
    model_file = request.files['model']
    if model_file.filename == '':
        return _error('No selected file', 400)
    if not allowed_file(model_file.filename):
        return _error('File type not allowed', 400)
    filename = secure_filename(model_file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    model_file.save(filepath)
    model_id = model_server.load_model(filepath)
    if model_id:
        return (jsonify({'model_id': model_id}), 200)
    return _error('Model upload failed', 400)


@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()
    if not data or 'model_id' not in data or 'input_data' not in data:
        return _error('Invalid request', 400)
    prediction_id = model_server.predict(data['model_id'], data['input_data'])
    if prediction_id:
        return (jsonify({'prediction_id': prediction_id}), 200)
    return _error('Prediction failed', 400)


@app.route('/prediction/<prediction_id>', methods=['GET'])
def get_prediction(prediction_id):
    if prediction_id in model_server.predictions:
        return (jsonify({'prediction': model_server.predictions[prediction_id]}), 200)
    return _error('Prediction not found', 404)


@app.route('/models', methods=['GET'])
def list_models():
    return (jsonify({'models': list(model_server.loaded_models.keys())}), 200)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
