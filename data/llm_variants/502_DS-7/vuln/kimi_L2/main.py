"""Flask service for running pluggable analysis modules over uploaded data."""

import pickle
import json
from dataclasses import dataclass
from io import BytesIO

import numpy as np
from flask import Flask, jsonify, request


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServerConfig:
    """Runtime settings for the Flask development server."""

    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False


SERVER_CONFIG = ServerConfig()

# HTTP status codes returned by the API.
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

# Error messages returned by the API.
ERROR_NO_DATA_FILE = 'No data file provided'
ERROR_NO_MODULE_FILE = 'No module file provided'
ERROR_INVALID_REQUEST = 'Invalid request'
ERROR_DATA_UPLOAD_FAILED = 'Data upload failed'
ERROR_MODULE_UPLOAD_FAILED = 'Module upload failed'
ERROR_ANALYSIS_FAILED = 'Analysis failed'
ERROR_ANALYSIS_NOT_FOUND = 'Analysis not found'

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _success_response(payload):
    return (jsonify(payload), HTTP_OK)


def _error_response(message, status_code):
    return (jsonify({'error': message}), status_code)


def _log_failure(operation, error):
    print(f'{operation} failed: {error}')


def _serialize_result(result):
    if isinstance(result, np.ndarray):
        return result.tolist()
    return result


# ---------------------------------------------------------------------------
# Core analysis store
# ---------------------------------------------------------------------------

class DataAnalyzer:
    """In-memory store for uploaded data, analysis modules and results."""

    def __init__(self):
        self.analyses = {}
        self.data_cache = {}
        self.analysis_modules = {}

    def load_analysis_module(self, module_data):
        try:
            module = pickle.loads(module_data)
            module_id = self._derive_module_id(module, module_data)
            self.analysis_modules[module_id] = module
            return module_id
        except Exception as e:
            _log_failure('Module loading', e)
            return None

    def analyze_data(self, data_id, module_id, parameters):
        if module_id not in self.analysis_modules:
            return None
        try:
            data = self.data_cache.get(data_id)
            if data is None:
                return None
            module = self.analysis_modules[module_id]
            result = module.analyze(data, **parameters)
            analysis_id = self._derive_analysis_id(data_id, module_id, parameters)
            self.analyses[analysis_id] = self._build_analysis_record(
                data_id, module_id, parameters, result
            )
            return analysis_id
        except Exception as e:
            _log_failure('Analysis', e)
            return None

    def upload_data(self, data_bytes):
        try:
            data = self._load_numpy_payload(data_bytes)
            data_id = self._derive_data_id(data_bytes)
            self.data_cache[data_id] = data
            return data_id
        except Exception as e:
            _log_failure('Data upload', e)
            return None

    @staticmethod
    def _load_numpy_payload(data_bytes):
        return np.load(BytesIO(data_bytes), allow_pickle=True)

    @staticmethod
    def _derive_data_id(data_bytes):
        return str(hash(data_bytes))

    @staticmethod
    def _derive_module_id(module, module_data):
        if hasattr(module, '__name__'):
            return module.__name__
        return str(hash(module_data))

    @staticmethod
    def _derive_analysis_id(data_id, module_id, parameters):
        return f'{data_id}_{module_id}_{hash(str(parameters))}'

    @staticmethod
    def _build_analysis_record(data_id, module_id, parameters, result):
        return {
            'data_id': data_id,
            'module_id': module_id,
            'parameters': parameters,
            'result': result,
        }


analyzer = DataAnalyzer()


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

@app.route('/upload_data', methods=['POST'])
def upload_data():
    if 'data' not in request.files:
        return _error_response(ERROR_NO_DATA_FILE, HTTP_BAD_REQUEST)
    data_file = request.files['data'].read()
    data_id = analyzer.upload_data(data_file)
    if data_id:
        return _success_response({'data_id': data_id})
    return _error_response(ERROR_DATA_UPLOAD_FAILED, HTTP_BAD_REQUEST)


@app.route('/upload_module', methods=['POST'])
def upload_module():
    if 'module' not in request.files:
        return _error_response(ERROR_NO_MODULE_FILE, HTTP_BAD_REQUEST)
    module_file = request.files['module'].read()
    module_id = analyzer.load_analysis_module(module_file)
    if module_id:
        return _success_response({'module_id': module_id})
    return _error_response(ERROR_MODULE_UPLOAD_FAILED, HTTP_BAD_REQUEST)


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    if not data or 'data_id' not in data or 'module_id' not in data:
        return _error_response(ERROR_INVALID_REQUEST, HTTP_BAD_REQUEST)
    parameters = data.get('parameters', {})
    analysis_id = analyzer.analyze_data(
        data['data_id'], data['module_id'], parameters
    )
    if analysis_id:
        return _success_response({'analysis_id': analysis_id})
    return _error_response(ERROR_ANALYSIS_FAILED, HTTP_BAD_REQUEST)


@app.route('/results/<analysis_id>', methods=['GET'])
def get_results(analysis_id):
    if analysis_id in analyzer.analyses:
        result = _serialize_result(analyzer.analyses[analysis_id]['result'])
        return _success_response({'result': result})
    return _error_response(ERROR_ANALYSIS_NOT_FOUND, HTTP_NOT_FOUND)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app.run(
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug,
    )


if __name__ == '__main__':
    main()
