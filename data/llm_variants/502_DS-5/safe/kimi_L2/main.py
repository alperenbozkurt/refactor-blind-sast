"""File processing service with dynamically loadable processing plugins.

Exposes a small Flask API for uploading plugins, processing files with
them and downloading the processed results.
"""

import hashlib
import importlib.util
import json
import os
import shutil
import tempfile
from dataclasses import dataclass

from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StorageConfig:
    """Filesystem locations used by the service."""
    upload_folder: str = './uploads'
    processed_folder: str = './processed'
    plugin_folder: str = './plugins'


@dataclass(frozen=True)
class ServerConfig:
    """Settings used when running the HTTP server."""
    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = False


STORAGE = StorageConfig()
SERVER = ServerConfig()

PLUGIN_MODULE_NAME = 'plugin_module'
PLUGIN_TEMP_FILENAME = 'plugin.py'
PLUGIN_EXTENSION = '.py'
PROCESSED_SUFFIX = '.processed'

ALLOWED_PLUGIN_METHODS = ['process']

RESTRICTED_BUILTINS = {
    'str': str,
    'bytes': bytes,
    'len': len,
    'int': int,
    'range': range,
}

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _ensure_directories(*paths):
    """Create each directory in *paths* if it does not already exist."""
    for path in paths:
        os.makedirs(path, exist_ok=True)


def _error_response(message, status_code):
    """Build a JSON error body paired with an HTTP status code."""
    return jsonify({'error': message}), status_code


def _restricted_builtins():
    """Return a fresh copy of the builtins exposed to plugin code."""
    return dict(RESTRICTED_BUILTINS)


def _load_module(module_path):
    """Execute the Python file at *module_path* with restricted builtins."""
    spec = importlib.util.spec_from_file_location(PLUGIN_MODULE_NAME, module_path)
    module = importlib.util.module_from_spec(spec)
    module.__dict__['__builtins__'] = _restricted_builtins()
    spec.loader.exec_module(module)
    return module


def _md5_hexdigest(file_path):
    """Return the MD5 hex digest of the contents of *file_path*."""
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = STORAGE.upload_folder
app.config['PROCESSED_FOLDER'] = STORAGE.processed_folder
app.config['PLUGIN_FOLDER'] = STORAGE.plugin_folder

_ensure_directories(
    app.config['UPLOAD_FOLDER'],
    app.config['PROCESSED_FOLDER'],
    app.config['PLUGIN_FOLDER'],
)


# ---------------------------------------------------------------------------
# Processing core
# ---------------------------------------------------------------------------


class FileProcessor:
    """Loads processing plugins and applies them to uploaded files."""

    def __init__(self):
        self.jobs = {}
        self.plugins = {}
        self.allowed_plugin_methods = list(ALLOWED_PLUGIN_METHODS)

    def _generate_job_id(self, filename):
        return hashlib.sha256(filename.encode()).hexdigest()

    def _validate_plugin(self, plugin_module):
        if not all(hasattr(plugin_module, method) for method in self.allowed_plugin_methods):
            raise ValueError('Plugin missing required methods')

    @staticmethod
    def _read_bytes(path):
        with open(path, 'rb') as f:
            return f.read()

    @staticmethod
    def _write_processed_file(source_filepath, data):
        output_filename = os.path.join(
            app.config['PROCESSED_FOLDER'],
            os.path.basename(source_filepath) + PROCESSED_SUFFIX,
        )
        with open(output_filename, 'wb') as f:
            f.write(data)
        return output_filename

    def load_processing_plugin(self, plugin_file):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = os.path.join(temp_dir, PLUGIN_TEMP_FILENAME)
                plugin_file.save(temp_path)
                plugin_module = _load_module(temp_path)
                self._validate_plugin(plugin_module)
                plugin_id = _md5_hexdigest(temp_path)
                final_path = os.path.join(
                    app.config['PLUGIN_FOLDER'],
                    plugin_id + PLUGIN_EXTENSION,
                )
                shutil.move(temp_path, final_path)
                self.plugins[plugin_id] = final_path
                return plugin_id
        except Exception as e:
            print(f'Plugin loading failed: {e}')
            return None

    def process_file(self, filepath, plugin_id):
        if plugin_id not in self.plugins:
            return None
        try:
            plugin_module = _load_module(self.plugins[plugin_id])
            file_data = self._read_bytes(filepath)
            result = plugin_module.process(file_data)
            if not isinstance(result, bytes):
                raise ValueError('Plugin must return bytes')
            return self._write_processed_file(filepath, result)
        except Exception as e:
            print(f'File processing failed: {e}')
            return None


processor = FileProcessor()

# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------


@app.route('/upload_plugin', methods=['POST'])
def upload_plugin():
    if 'plugin' not in request.files:
        return _error_response('No plugin file provided', HTTP_BAD_REQUEST)
    plugin_file = request.files['plugin']
    if plugin_file.filename == '':
        return _error_response('Empty filename', HTTP_BAD_REQUEST)
    if not plugin_file.filename.endswith(PLUGIN_EXTENSION):
        return _error_response('Only Python files (.py) are allowed', HTTP_BAD_REQUEST)
    plugin_id = processor.load_processing_plugin(plugin_file)
    if plugin_id:
        return jsonify({'plugin_id': plugin_id}), HTTP_OK
    return _error_response('Plugin upload failed', HTTP_BAD_REQUEST)


@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return _error_response('No file provided', HTTP_BAD_REQUEST)
    if 'plugin_id' not in request.form:
        return _error_response('No plugin ID provided', HTTP_BAD_REQUEST)
    file = request.files['file']
    if file.filename == '':
        return _error_response('Empty filename', HTTP_BAD_REQUEST)
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    processed_file = processor.process_file(filepath, request.form['plugin_id'])
    if processed_file:
        processed_basename = os.path.basename(processed_file)
        return jsonify({
            'processed_file': processed_basename,
            'download_url': f'/download/{processed_basename}',
        }), HTTP_OK
    return _error_response('File processing failed', HTTP_INTERNAL_SERVER_ERROR)


@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    filepath = os.path.join(app.config['PROCESSED_FOLDER'], secure_filename(filename))
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return _error_response('File not found', HTTP_NOT_FOUND)


@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        'plugins_loaded': len(processor.plugins),
        'jobs_processed': len(processor.jobs),
    }), HTTP_OK


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------


def main():
    app.run(host=SERVER.host, port=SERVER.port, debug=SERVER.debug)


if __name__ == '__main__':
    main()
