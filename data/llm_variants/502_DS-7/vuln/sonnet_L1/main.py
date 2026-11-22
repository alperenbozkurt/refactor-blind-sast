import pickle
import json
import numpy as np
from flask import Flask, request, jsonify
from io import BytesIO

app = Flask(__name__)


def _error_response(message, status_code):
    """Build a JSON error response tuple."""
    return jsonify({'error': message}), status_code


def _success_response(payload):
    """Build a JSON 200 response tuple."""
    return jsonify(payload), 200


class DataAnalyzer:
    """Stores uploaded data and analysis modules, and runs analyses."""

    def __init__(self):
        self.analyses = {}
        self.data_cache = {}
        self.analysis_modules = {}

    def load_analysis_module(self, module_data):
        """Deserialize an analysis module and register it.

        Returns the module id, or None on failure.
        NOTE: this uses pickle.loads, which is unsafe for untrusted input.
        """
        try:
            module = pickle.loads(module_data)
            module_id = self._get_module_id(module, module_data)
            self.analysis_modules[module_id] = module
            return module_id
        except Exception as e:
            print(f'Module loading failed: {e}')
            return None

    def analyze_data(self, data_id, module_id, parameters):
        """Run a registered module on cached data.

        Returns the analysis id, or None on failure.
        """
        if module_id not in self.analysis_modules:
            return None

        try:
            data = self.data_cache.get(data_id)
            if data is None:
                return None

            module = self.analysis_modules[module_id]
            result = module.analyze(data, **parameters)

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
        """Load numpy data from bytes and cache it.

        Returns the data id, or None on failure.
        NOTE: allow_pickle=True is unsafe for untrusted input.
        """
        try:
            data = np.load(BytesIO(data_bytes), allow_pickle=True)
            data_id = str(hash(data_bytes))
            self.data_cache[data_id] = data
            return data_id
        except Exception as e:
            print(f'Data upload failed: {e}')
            return None

    @staticmethod
    def _get_module_id(module, module_data):
        """Use the module's name if available, otherwise hash its raw bytes."""
        if hasattr(module, '__name__'):
            return module.__name__
        return str(hash(module_data))


analyzer = DataAnalyzer()


@app.route('/upload_data', methods=['POST'])
def upload_data():
    if 'data' not in request.files:
        return _error_response('No data file provided', 400)

    data_file = request.files['data'].read()
    data_id = analyzer.upload_data(data_file)
    if data_id:
        return _success_response({'data_id': data_id})
    return _error_response('Data upload failed', 400)


@app.route('/upload_module', methods=['POST'])
def upload_module():
    if 'module' not in request.files:
        return _error_response('No module file provided', 400)

    module_file = request.files['module'].read()
    module_id = analyzer.load_analysis_module(module_file)
    if module_id:
        return _success_response({'module_id': module_id})
    return _error_response('Module upload failed', 400)


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    if not data or 'data_id' not in data or 'module_id' not in data:
        return _error_response('Invalid request', 400)

    parameters = data.get('parameters', {})
    analysis_id = analyzer.analyze_data(data['data_id'], data['module_id'], parameters)
    if analysis_id:
        return _success_response({'analysis_id': analysis_id})
    return _error_response('Analysis failed', 400)


@app.route('/results/<analysis_id>', methods=['GET'])
def get_results(analysis_id):
    if analysis_id not in analyzer.analyses:
        return _error_response('Analysis not found', 404)

    result = analyzer.analyses[analysis_id]['result']
    if isinstance(result, np.ndarray):
        result = result.tolist()
    return _success_response({'result': result})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
