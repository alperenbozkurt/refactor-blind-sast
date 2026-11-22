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
MODULE_DIR = './analysis_modules'
os.makedirs(MODULE_DIR, exist_ok=True)

_SAFE_BUILTINS = {
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

_ALLOWED_RESULT_TYPES = (str, int, float, bool, list, dict, tuple)


def _load_restricted_module(path):
    """Load a module from `path` with a restricted set of builtins."""
    spec = importlib.util.spec_from_file_location('analysis_module', path)
    module = importlib.util.module_from_spec(spec)
    module.__dict__['__builtins__'] = dict(_SAFE_BUILTINS)
    spec.loader.exec_module(module)
    return module


def _normalize_result(result):
    """Convert a result to a serialisable type or raise ValueError."""
    if isinstance(result, np.ndarray):
        return result.tolist()
    if not isinstance(result, _ALLOWED_RESULT_TYPES):
        raise ValueError('Invalid result type')
    return result


class DataAnalyzer:

    def __init__(self):
        self.analyses = {}
        self.data_cache = {}
        self.analysis_modules = {}
        self.allowed_module_methods = ['analyze']

    def load_analysis_module(self, module_file):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = os.path.join(temp_dir, 'module.py')
                module_file.save(temp_path)
                module = _load_restricted_module(temp_path)
                if not all(hasattr(module, method) for method in self.allowed_module_methods):
                    raise ValueError('Module missing required methods')
                with open(temp_path, 'rb') as f:
                    module_id = hashlib.sha256(f.read()).hexdigest()
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
            module = _load_restricted_module(self.analysis_modules[module_id])
            result = _normalize_result(module.analyze(data, **parameters))
            analysis_id = f'{data_id}_{module_id}_{hash(str(parameters))}'
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


def _error(message, status):
    return (jsonify({'error': message}), status)


def _validate_upload(field, missing_message, extension, extension_message):
    """Return (file, None) if valid, otherwise (None, error_response)."""
    if field not in request.files:
        return None, _error(missing_message, 400)
    uploaded = request.files[field]
    if uploaded.filename == '':
        return None, _error('Empty filename', 400)
    if not uploaded.filename.endswith(extension):
        return None, _error(extension_message, 400)
    return uploaded, None


@app.route('/upload_data', methods=['POST'])
def upload_data():
    data_file, error = _validate_upload(
        'data', 'No data file provided', '.npy', 'Only .npy files are allowed')
    if error:
        return error
    data_id = analyzer.upload_data(data_file.read())
    if data_id:
        return (jsonify({'data_id': data_id}), 200)
    return _error('Data upload failed', 400)


@app.route('/upload_module', methods=['POST'])
def upload_module():
    module_file, error = _validate_upload(
        'module', 'No module file provided', '.py',
        'Only Python files (.py) are allowed')
    if error:
        return error
    module_id = analyzer.load_analysis_module(module_file)
    if module_id:
        return (jsonify({'module_id': module_id}), 200)
    return _error('Module upload failed', 400)


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    if not data or 'data_id' not in data or 'module_id' not in data:
        return _error('Invalid request', 400)
    parameters = data.get('parameters', {})
    analysis_id = analyzer.analyze_data(data['data_id'], data['module_id'], parameters)
    if analysis_id:
        return (jsonify({'analysis_id': analysis_id}), 200)
    return _error('Analysis failed', 400)


@app.route('/results/<analysis_id>', methods=['GET'])
def get_results(analysis_id):
    if analysis_id in analyzer.analyses:
        return (jsonify({'result': analyzer.analyses[analysis_id]['result']}), 200)
    return _error('Analysis not found', 404)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
