"""File processing web service.

A Flask application that accepts pickled processing plugins and uploaded
files, applies a selected plugin to each uploaded file, and serves the
processed results for download.
"""

import hashlib
import json
import os
import pickle

from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Storage locations (also exposed through the Flask config for handlers).
UPLOAD_FOLDER = './uploads'
PROCESSED_FOLDER = './processed'

# Server settings for the command-line entry point.
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
DEBUG_MODE = False

# HTTP status codes used by the API.
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500

# Routes.
ROUTE_UPLOAD_PLUGIN = '/upload_plugin'
ROUTE_UPLOAD_FILE = '/upload_file'
ROUTE_DOWNLOAD = '/download/<filename>'
ROUTE_STATUS = '/status'

# Request field names.
PLUGIN_FILE_FIELD = 'plugin'
UPLOAD_FILE_FIELD = 'file'
PLUGIN_ID_FIELD = 'plugin_id'

# Response payload keys and error messages.
ERROR_KEY = 'error'
MSG_NO_PLUGIN_FILE = 'No plugin file provided'
MSG_PLUGIN_UPLOAD_FAILED = 'Plugin upload failed'
MSG_NO_FILE_PROVIDED = 'No file provided'
MSG_NO_PLUGIN_ID = 'No plugin ID provided'
MSG_EMPTY_FILENAME = 'Empty filename'
MSG_PROCESSING_FAILED = 'File processing failed'
MSG_FILE_NOT_FOUND = 'File not found'

# File handling.
PROCESSED_SUFFIX = '.processed'
DOWNLOAD_URL_PREFIX = '/download/'

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER


def _ensure_storage_directories():
    """Create the upload and processed directories if they do not exist."""
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)


_ensure_storage_directories()


def _error_response(message, status_code):
    """Build a consistent JSON error response tuple."""
    return (jsonify({ERROR_KEY: message}), status_code)


# ---------------------------------------------------------------------------
# Processing core
# ---------------------------------------------------------------------------

class FileProcessor:

    """Registry of processing plugins and file processing jobs."""

    def __init__(self):
        self.jobs = {}
        self.plugins = {}

    def _generate_job_id(self, filename):
        return hashlib.sha256(filename.encode()).hexdigest()

    def load_processing_plugin(self, plugin_data):
        try:
            plugin = pickle.loads(plugin_data)
            plugin_id = hashlib.md5(plugin_data).hexdigest()
            self.plugins[plugin_id] = plugin
            return plugin_id
        except Exception as e:
            print(f'Plugin loading failed: {e}')
            return None

    def process_file(self, filepath, plugin_id):
        if plugin_id not in self.plugins:
            return None
        try:
            plugin = self.plugins[plugin_id]
            file_data = self._read_binary(filepath)
            result = plugin.process(file_data)
            output_filename = self._processed_path(filepath)
            self._write_binary(output_filename, result)
            return output_filename
        except Exception as e:
            print(f'File processing failed: {e}')
            return None

    @staticmethod
    def _read_binary(filepath):
        with open(filepath, 'rb') as f:
            return f.read()

    @staticmethod
    def _write_binary(filepath, data):
        with open(filepath, 'wb') as f:
            f.write(data)

    @staticmethod
    def _processed_path(filepath):
        output_name = os.path.basename(filepath) + PROCESSED_SUFFIX
        return os.path.join(app.config['PROCESSED_FOLDER'], output_name)


processor = FileProcessor()

# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------


def _processed_file_payload(processed_file):
    """Build the success payload returned after a file is processed."""
    basename = os.path.basename(processed_file)
    return {
        'processed_file': basename,
        'download_url': f'{DOWNLOAD_URL_PREFIX}{basename}',
    }


@app.route(ROUTE_UPLOAD_PLUGIN, methods=['POST'])
def upload_plugin():
    if PLUGIN_FILE_FIELD not in request.files:
        return _error_response(MSG_NO_PLUGIN_FILE, HTTP_BAD_REQUEST)
    plugin_file = request.files[PLUGIN_FILE_FIELD].read()
    plugin_id = processor.load_processing_plugin(plugin_file)
    if plugin_id:
        return (jsonify({PLUGIN_ID_FIELD: plugin_id}), HTTP_OK)
    return _error_response(MSG_PLUGIN_UPLOAD_FAILED, HTTP_BAD_REQUEST)


@app.route(ROUTE_UPLOAD_FILE, methods=['POST'])
def upload_file():
    if UPLOAD_FILE_FIELD not in request.files:
        return _error_response(MSG_NO_FILE_PROVIDED, HTTP_BAD_REQUEST)
    if PLUGIN_ID_FIELD not in request.form:
        return _error_response(MSG_NO_PLUGIN_ID, HTTP_BAD_REQUEST)
    file = request.files[UPLOAD_FILE_FIELD]
    if file.filename == '':
        return _error_response(MSG_EMPTY_FILENAME, HTTP_BAD_REQUEST)
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    processed_file = processor.process_file(filepath, request.form[PLUGIN_ID_FIELD])
    if processed_file:
        return (jsonify(_processed_file_payload(processed_file)), HTTP_OK)
    return _error_response(MSG_PROCESSING_FAILED, HTTP_INTERNAL_ERROR)


@app.route(ROUTE_DOWNLOAD, methods=['GET'])
def download_file(filename):
    filepath = os.path.join(app.config['PROCESSED_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return _error_response(MSG_FILE_NOT_FOUND, HTTP_NOT_FOUND)


@app.route(ROUTE_STATUS, methods=['GET'])
def status():
    return (jsonify({
        'plugins_loaded': len(processor.plugins),
        'jobs_processed': len(processor.jobs),
    }), HTTP_OK)


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def main():
    """Start the HTTP server."""
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=DEBUG_MODE)


if __name__ == '__main__':
    main()
