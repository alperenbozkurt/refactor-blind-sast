import json
import numpy as np
from flask import Flask, request, jsonify
from io import BytesIO
import importlib.util
import tempfile
import shutil
import os
import hashlib

# ---------------------------------------------------------------------------
# Application and configuration
# ---------------------------------------------------------------------------

app = Flask(__name__)

MODULE_DIR = './analysis_modules'
os.makedirs(MODULE_DIR, exist_ok=True)


class ServerConfig:
    """Settings used when running the built-in Flask server."""

    HOST = '0.0.0.0'
    PORT = 5000
    DEBUG = False


# Module handling constants.
ANALYSIS_MODULE_SPEC_NAME = 'analysis_module'
TEMP_MODULE_FILENAME = 'module.py'
MODULE_FILE_EXTENSION = '.py'
DATA_FILE_EXTENSION = '.npy'

# Result types an analysis module is allowed to return.
ALLOWED_RESULT_TYPES = (str, int, float, bool, list, dict, tuple)

# HTTP status codes used by the routes.
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

# API error messages.
ERROR_NO_DATA_FILE = 'No data file provided'
ERROR_NO_MODULE_FILE = 'No module file provided'
ERROR_EMPTY_FILENAME = 'Empty filename'
ERROR_INVALID_DATA_FILE = 'Only .npy files are allowed'
ERROR_INVALID_MODULE_FILE = 'Only Python files (.py) are allowed'
ERROR_DATA_UPLOAD_FAILED = 'Data upload failed'
ERROR_MODULE_UPLOAD_FAILED = 'Module upload failed'
ERROR_INVALID_REQUEST = 'Invalid request'
ERROR_ANALYSIS_FAILED = 'Analysis failed'
ERROR_ANALYSIS_NOT_FOUND = 'Analysis not found'


# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

def _restricted_builtins():
    """Return a fresh restricted ``__builtins__`` mapping for a module."""
    return {
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'list': list,
        'dict': dict,
        'tuple': tuple,
        'range': range,
        'len': len,
        'sum': sum,
        'min': min,
        'max': max,
        'abs': abs,
        'round': round,
    }


def _load_analysis_module(module_path):
    """Execute an analysis module from ``module_path`` with restricted builtins."""
    spec = importlib.util.spec_from_file_location(ANALYSIS_MODULE_SPEC_NAME, module_path)
    module = importlib.util.module_from_spec(spec)
    module.__dict__['__builtins__'] = _restricted_builtins()
    spec.loader.exec_module(module)
    return module


def _hash_file_contents(path):
    """Return the SHA-256 hex digest of the file at ``path``."""
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def _normalize_result(result):
    """Convert numpy arrays to lists and validate the analysis result type."""
    if isinstance(result, np.ndarray):
        return result.tolist()
    if not isinstance(result, ALLOWED_RESULT_TYPES):
        raise ValueError('Invalid result type')
    return result


# ---------------------------------------------------------------------------
# Core analyzer
# ---------------------------------------------------------------------------

class DataAnalyzer:

    def __init__(self):
        self.analyses = {}
        self.data_cache = {}
        self.analysis_modules = {}
        self.allowed_module_methods = ['analyze']

    def load_analysis_module(self, module_file):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = os.path.join(temp_dir, TEMP_MODULE_FILENAME)
                module_file.save(temp_path)
                module = _load_analysis_module(temp_path)
                self._validate_module(module)
                return self._register_module(temp_path)
        except Exception as e:
            print(f'Module loading failed: {e}')
            return None

    def _validate_module(self, module):
        if not all((hasattr(module, method) for method in self.allowed_module_methods)):
            raise ValueError('Module missing required methods')

    def _register_module(self, temp_path):
        module_id = _hash_file_contents(temp_path)
        final_path = os.path.join(MODULE_DIR, f'{module_id}.py')
        shutil.move(temp_path, final_path)
        self.analysis_modules[module_id] = final_path
        return module_id

    def analyze_data(self, data_id, module_id, parameters):
        if module_id not in self.analysis_modules:
            return None
        try:
            data = self.data_cache.get(data_id)
            if data is None:
                return None
            module_path = self.analysis_modules[module_id]
            module = _load_analysis_module(module_path)
            result = _normalize_result(module.analyze(data, **parameters))
            analysis_id = self._build_analysis_id(data_id, module_id, parameters)
            self.analyses[analysis_id] = {
                'data_id': data_id,
                'module_id': module_id,
                'parameters': parameters,
                'result': result,
            }
            return analysis_id
        except Exception as e:
            print(f'Analysis failed: {e}')
            return None

    @staticmethod
    def _build_analysis_id(data_id, module_id, parameters):
        return f'{data_id}_{module_id}_{hash(str(parameters))}'

    def upload_data(self, data_bytes):
        try:
            data = np.load(BytesIO(data_bytes), allow_pickle=False)
            data_id = str(hash(data_bytes))
            self.data_cache[data_id] = data
            return data_id
        except Exception as e:
            print(f'Data upload failed: {e}')
            return None


analyzer = DataAnalyzer()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _get_uploaded_file(field_name, extension, missing_error, invalid_type_error):
    """Validate and return the uploaded file, or ``(None, error_response)``."""
    if field_name not in request.files:
        return None, _error_response(missing_error, HTTP_BAD_REQUEST)
    uploaded_file = request.files[field_name]
    if uploaded_file.filename == '':
        return None, _error_response(ERROR_EMPTY_FILENAME, HTTP_BAD_REQUEST)
    if not uploaded_file.filename.endswith(extension):
        return None, _error_response(invalid_type_error, HTTP_BAD_REQUEST)
    return uploaded_file, None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/upload_data', methods=['POST'])
def upload_data():
    data_file, error = _get_uploaded_file('data', DATA_FILE_EXTENSION, ERROR_NO_DATA_FILE, ERROR_INVALID_DATA_FILE)
    if error is not None:
        return error
    data_id = analyzer.upload_data(data_file.read())
    if data_id:
        return (jsonify({'data_id': data_id}), HTTP_OK)
    return _error_response(ERROR_DATA_UPLOAD_FAILED, HTTP_BAD_REQUEST)


@app.route('/upload_module', methods=['POST'])
def upload_module():
    module_file, error = _get_uploaded_file('module', MODULE_FILE_EXTENSION, ERROR_NO_MODULE_FILE, ERROR_INVALID_MODULE_FILE)
    if error is not None:
        return error
    module_id = analyzer.load_analysis_module(module_file)
    if module_id:
        return (jsonify({'module_id': module_id}), HTTP_OK)
    return _error_response(ERROR_MODULE_UPLOAD_FAILED, HTTP_BAD_REQUEST)


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    if not data or 'data_id' not in data or 'module_id' not in data:
        return _error_response(ERROR_INVALID_REQUEST, HTTP_BAD_REQUEST)
    parameters = data.get('parameters', {})
    analysis_id = analyzer.analyze_data(data['data_id'], data['module_id'], parameters)
    if analysis_id:
        return (jsonify({'analysis_id': analysis_id}), HTTP_OK)
    return _error_response(ERROR_ANALYSIS_FAILED, HTTP_BAD_REQUEST)


@app.route('/results/<analysis_id>', methods=['GET'])
def get_results(analysis_id):
    if analysis_id in analyzer.analyses:
        return (jsonify({'result': analyzer.analyses[analysis_id]['result']}), HTTP_OK)
    return _error_response(ERROR_ANALYSIS_NOT_FOUND, HTTP_NOT_FOUND)


if __name__ == '__main__':
    app.run(host=ServerConfig.HOST, port=ServerConfig.PORT, debug=ServerConfig.DEBUG)
