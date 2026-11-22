import json
import numpy as np
from flask import Flask, request, jsonify
from io import BytesIO
import importlib.util
import tempfile
import shutil
import os
import hashlib

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #
MODULE_DIR = './analysis_modules'
os.makedirs(MODULE_DIR, exist_ok=True)

TEMP_MODULE_FILENAME = 'module.py'
ANALYSIS_MODULE_NAME = 'analysis_module'
ALLOWED_MODULE_METHODS = ['analyze']
ALLOWED_RESULT_TYPES = (str, int, float, bool, list, dict, tuple)

DATA_FILE_EXTENSION = '.npy'
MODULE_FILE_EXTENSION = '.py'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = False


def _build_restricted_builtins():
    """Return a fresh dict of builtins exposed to uploaded analysis modules."""
    return {
        'str': str, 'int': int, 'float': float, 'bool': bool,
        'list': list, 'dict': dict, 'tuple': tuple, 'range': range,
        'len': len, 'sum': sum, 'min': min, 'max': max,
        'abs': abs, 'round': round,
    }


def _load_module_from_path(path):
    """Load a Python file as a module with restricted builtins and execute it."""
    spec = importlib.util.spec_from_file_location(ANALYSIS_MODULE_NAME, path)
    module = importlib.util.module_from_spec(spec)
    module.__dict__['__builtins__'] = _build_restricted_builtins()
    spec.loader.exec_module(module)
    return module


def _compute_file_sha256(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def _normalize_result(result):
    """Convert an analysis result into a JSON-friendly value or raise."""
    if isinstance(result, np.ndarray):
        return result.tolist()
    if not isinstance(result, ALLOWED_RESULT_TYPES):
        raise ValueError('Invalid result type')
    return result


def _build_analysis_id(data_id, module_id, parameters):
    return f'{data_id}_{module_id}_{hash(str(parameters))}'


class DataAnalyzer:

    def __init__(self):
        self.analyses = {}
        self.data_cache = {}
        self.analysis_modules = {}
        self.allowed_module_methods = list(ALLOWED_MODULE_METHODS)

    def _module_has_required_methods(self, module):
        return all((hasattr(module, method) for method in self.allowed_module_methods))

    def load_analysis_module(self, module_file):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = os.path.join(temp_dir, TEMP_MODULE_FILENAME)
                module_file.save(temp_path)
                module = _load_module_from_path(temp_path)
                if not self._module_has_required_methods(module):
                    raise ValueError('Module missing required methods')
                module_id = _compute_file_sha256(temp_path)
                final_path = os.path.join(MODULE_DIR, f'{module_id}.py')
                shutil.move(temp_path, final_path)
                self.analysis_modules[module_id] = final_path
                return module_id
        except Exception as e:
            print(f'Module loading failed: {e}')
            return None

    def analyze_data(self, data_id, module_id, parameters):
        if module_id not in self.analysis_modules:
            return None
        try:
            data = self.data_cache.get(data_id)
            if data is None:
                return None
            module = _load_module_from_path(self.analysis_modules[module_id])
            result = _normalize_result(module.analyze(data, **parameters))
            analysis_id = _build_analysis_id(data_id, module_id, parameters)
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


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _extract_uploaded_file(field, missing_message, extension, extension_message):
    """Validate an uploaded file; return (file, error_response)."""
    if field not in request.files:
        return None, _error_response(missing_message, 400)
    uploaded = request.files[field]
    if uploaded.filename == '':
        return None, _error_response('Empty filename', 400)
    if not uploaded.filename.endswith(extension):
        return None, _error_response(extension_message, 400)
    return uploaded, None


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/upload_data', methods=['POST'])
def upload_data():
    data_file, error = _extract_uploaded_file(
        'data',
        'No data file provided',
        DATA_FILE_EXTENSION,
        'Only .npy files are allowed',
    )
    if error:
        return error
    data_id = analyzer.upload_data(data_file.read())
    if data_id:
        return (jsonify({'data_id': data_id}), 200)
    return _error_response('Data upload failed', 400)


@app.route('/upload_module', methods=['POST'])
def upload_module():
    module_file, error = _extract_uploaded_file(
        'module',
        'No module file provided',
        MODULE_FILE_EXTENSION,
        'Only Python files (.py) are allowed',
    )
    if error:
        return error
    module_id = analyzer.load_analysis_module(module_file)
    if module_id:
        return (jsonify({'module_id': module_id}), 200)
    return _error_response('Module upload failed', 400)


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    if not data or 'data_id' not in data or 'module_id' not in data:
        return _error_response('Invalid request', 400)
    parameters = data.get('parameters', {})
    analysis_id = analyzer.analyze_data(data['data_id'], data['module_id'], parameters)
    if analysis_id:
        return (jsonify({'analysis_id': analysis_id}), 200)
    return _error_response('Analysis failed', 400)


@app.route('/results/<analysis_id>', methods=['GET'])
def get_results(analysis_id):
    if analysis_id in analyzer.analyses:
        return (jsonify({'result': analyzer.analyses[analysis_id]['result']}), 200)
    return _error_response('Analysis not found', 404)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
