import pickle
import json
import numpy as np
from dataclasses import dataclass
from flask import Flask, request, jsonify
from io import BytesIO

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Configuration and constants
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServerConfig:
    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False


SERVER_CONFIG = ServerConfig()

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

FILE_FIELD_DATA = 'data'
FILE_FIELD_MODULE = 'module'

ERR_NO_DATA_FILE = 'No data file provided'
ERR_NO_MODULE_FILE = 'No module file provided'
ERR_DATA_UPLOAD_FAILED = 'Data upload failed'
ERR_MODULE_UPLOAD_FAILED = 'Module upload failed'
ERR_INVALID_REQUEST = 'Invalid request'
ERR_ANALYSIS_FAILED = 'Analysis failed'
ERR_ANALYSIS_NOT_FOUND = 'Analysis not found'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _ok_response(payload):
    return (jsonify(payload), HTTP_OK)


def _log_failure(description, exc):
    print(f'{description}: {exc}')


def _deserialize_module(module_data):
    # SECURITY WARNING: pickle.loads on untrusted input allows arbitrary code
    # execution. Behaviour is preserved here; only use with trusted sources.
    return pickle.loads(module_data)


def _derive_module_id(module, module_data):
    if hasattr(module, '__name__'):
        return module.__name__
    return str(hash(module_data))


def _load_array(data_bytes):
    # SECURITY WARNING: allow_pickle=True permits arbitrary code execution
    # when loading untrusted input. Behaviour is preserved here.
    return np.load(BytesIO(data_bytes), allow_pickle=True)


def _build_analysis_id(data_id, module_id, parameters):
    return f'{data_id}_{module_id}_{hash(str(parameters))}'


def _serialize_result(result):
    if isinstance(result, np.ndarray):
        return result.tolist()
    return result


def _is_valid_analyze_request(payload):
    return bool(payload) and 'data_id' in payload and 'module_id' in payload


# ---------------------------------------------------------------------------
# Core domain class
# ---------------------------------------------------------------------------

class DataAnalyzer:

    def __init__(self):
        self.analyses = {}
        self.data_cache = {}
        self.analysis_modules = {}

    def load_analysis_module(self, module_data):
        try:
            module = _deserialize_module(module_data)
            module_id = _derive_module_id(module, module_data)
            self.analysis_modules[module_id] = module
            return module_id
        except Exception as e:
            _log_failure('Module loading failed', e)
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
            analysis_id = _build_analysis_id(data_id, module_id, parameters)
            self.analyses[analysis_id] = {
                'data_id': data_id,
                'module_id': module_id,
                'parameters': parameters,
                'result': result,
            }
            return analysis_id
        except Exception as e:
            _log_failure('Analysis failed', e)
            return None

    def upload_data(self, data_bytes):
        try:
            data = _load_array(data_bytes)
            data_id = str(hash(data_bytes))
            self.data_cache[data_id] = data
            return data_id
        except Exception as e:
            _log_failure('Data upload failed', e)
            return None


analyzer = DataAnalyzer()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/upload_data', methods=['POST'])
def upload_data():
    if FILE_FIELD_DATA not in request.files:
        return _error_response(ERR_NO_DATA_FILE, HTTP_BAD_REQUEST)
    data_file = request.files[FILE_FIELD_DATA].read()
    data_id = analyzer.upload_data(data_file)
    if data_id:
        return _ok_response({'data_id': data_id})
    return _error_response(ERR_DATA_UPLOAD_FAILED, HTTP_BAD_REQUEST)


@app.route('/upload_module', methods=['POST'])
def upload_module():
    if FILE_FIELD_MODULE not in request.files:
        return _error_response(ERR_NO_MODULE_FILE, HTTP_BAD_REQUEST)
    module_file = request.files[FILE_FIELD_MODULE].read()
    module_id = analyzer.load_analysis_module(module_file)
    if module_id:
        return _ok_response({'module_id': module_id})
    return _error_response(ERR_MODULE_UPLOAD_FAILED, HTTP_BAD_REQUEST)


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    if not _is_valid_analyze_request(data):
        return _error_response(ERR_INVALID_REQUEST, HTTP_BAD_REQUEST)
    parameters = data.get('parameters', {})
    analysis_id = analyzer.analyze_data(data['data_id'], data['module_id'], parameters)
    if analysis_id:
        return _ok_response({'analysis_id': analysis_id})
    return _error_response(ERR_ANALYSIS_FAILED, HTTP_BAD_REQUEST)


@app.route('/results/<analysis_id>', methods=['GET'])
def get_results(analysis_id):
    if analysis_id in analyzer.analyses:
        result = _serialize_result(analyzer.analyses[analysis_id]['result'])
        return _ok_response({'result': result})
    return _error_response(ERR_ANALYSIS_NOT_FOUND, HTTP_NOT_FOUND)


def main():
    app.run(host=SERVER_CONFIG.host, port=SERVER_CONFIG.port, debug=SERVER_CONFIG.debug)


if __name__ == '__main__':
    main()
