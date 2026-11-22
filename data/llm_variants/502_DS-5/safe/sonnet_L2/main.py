import json
import os
import hashlib
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
import importlib.util
import tempfile
import shutil

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
DEFAULT_UPLOAD_FOLDER = './uploads'
DEFAULT_PROCESSED_FOLDER = './processed'
DEFAULT_PLUGIN_FOLDER = './plugins'

PLUGIN_MODULE_NAME = 'plugin_module'
PLUGIN_TEMP_FILENAME = 'plugin.py'
PLUGIN_EXTENSION = '.py'
PROCESSED_SUFFIX = '.processed'
REQUIRED_PLUGIN_METHODS = ['process']

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = False


# --------------------------------------------------------------------------
# Application setup
# --------------------------------------------------------------------------
def _sandbox_builtins():
    """Return a fresh restricted builtins mapping for plugin modules."""
    return {'str': str, 'bytes': bytes, 'len': len, 'int': int, 'range': range}


def _configure_app(flask_app):
    flask_app.config['UPLOAD_FOLDER'] = DEFAULT_UPLOAD_FOLDER
    flask_app.config['PROCESSED_FOLDER'] = DEFAULT_PROCESSED_FOLDER
    flask_app.config['PLUGIN_FOLDER'] = DEFAULT_PLUGIN_FOLDER


def _ensure_directories(flask_app):
    for key in ('UPLOAD_FOLDER', 'PROCESSED_FOLDER', 'PLUGIN_FOLDER'):
        os.makedirs(flask_app.config[key], exist_ok=True)


app = Flask(__name__)
_configure_app(app)
_ensure_directories(app)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _load_sandboxed_module(path):
    """Load and execute the module at ``path`` with restricted builtins."""
    spec = importlib.util.spec_from_file_location(PLUGIN_MODULE_NAME, path)
    module = importlib.util.module_from_spec(spec)
    module.__dict__['__builtins__'] = _sandbox_builtins()
    spec.loader.exec_module(module)
    return module


def _md5_of_file(path):
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def _read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def _write_bytes(path, data):
    with open(path, 'wb') as f:
        f.write(data)


def _error(message, status_code):
    return (jsonify({'error': message}), status_code)


# --------------------------------------------------------------------------
# Core processor
# --------------------------------------------------------------------------
class FileProcessor:

    def __init__(self):
        self.jobs = {}
        self.plugins = {}
        self.allowed_plugin_methods = list(REQUIRED_PLUGIN_METHODS)

    def _generate_job_id(self, filename):
        return hashlib.sha256(filename.encode()).hexdigest()

    def _validate_plugin(self, plugin_module):
        if not all((hasattr(plugin_module, method) for method in self.allowed_plugin_methods)):
            raise ValueError('Plugin missing required methods')

    def load_processing_plugin(self, plugin_file):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = os.path.join(temp_dir, PLUGIN_TEMP_FILENAME)
                plugin_file.save(temp_path)
                plugin_module = _load_sandboxed_module(temp_path)
                self._validate_plugin(plugin_module)
                plugin_id = _md5_of_file(temp_path)
                final_path = os.path.join(app.config['PLUGIN_FOLDER'], f'{plugin_id}.py')
                shutil.move(temp_path, final_path)
                self.plugins[plugin_id] = final_path
                return plugin_id
        except Exception as e:
            print(f'Plugin loading failed: {e}')
            return None

    def _output_path_for(self, filepath):
        return os.path.join(app.config['PROCESSED_FOLDER'],
                            os.path.basename(filepath) + PROCESSED_SUFFIX)

    def process_file(self, filepath, plugin_id):
        if plugin_id not in self.plugins:
            return None
        try:
            plugin_module = _load_sandboxed_module(self.plugins[plugin_id])
            file_data = _read_bytes(filepath)
            result = plugin_module.process(file_data)
            if not isinstance(result, bytes):
                raise ValueError('Plugin must return bytes')
            output_filename = self._output_path_for(filepath)
            _write_bytes(output_filename, result)
            return output_filename
        except Exception as e:
            print(f'File processing failed: {e}')
            return None


processor = FileProcessor()


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route('/upload_plugin', methods=['POST'])
def upload_plugin():
    if 'plugin' not in request.files:
        return _error('No plugin file provided', 400)
    plugin_file = request.files['plugin']
    if plugin_file.filename == '':
        return _error('Empty filename', 400)
    if not plugin_file.filename.endswith(PLUGIN_EXTENSION):
        return _error('Only Python files (.py) are allowed', 400)
    plugin_id = processor.load_processing_plugin(plugin_file)
    if plugin_id:
        return (jsonify({'plugin_id': plugin_id}), 200)
    return _error('Plugin upload failed', 400)


@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return _error('No file provided', 400)
    if 'plugin_id' not in request.form:
        return _error('No plugin ID provided', 400)
    file = request.files['file']
    if file.filename == '':
        return _error('Empty filename', 400)
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    processed_file = processor.process_file(filepath, request.form['plugin_id'])
    if processed_file:
        processed_name = os.path.basename(processed_file)
        return (jsonify({'processed_file': processed_name,
                         'download_url': f'/download/{processed_name}'}), 200)
    return _error('File processing failed', 500)


@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    filepath = os.path.join(app.config['PROCESSED_FOLDER'], secure_filename(filename))
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return _error('File not found', 404)


@app.route('/status', methods=['GET'])
def status():
    return (jsonify({'plugins_loaded': len(processor.plugins),
                     'jobs_processed': len(processor.jobs)}), 200)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
