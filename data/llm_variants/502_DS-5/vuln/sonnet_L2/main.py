import pickle
import json
import os
import hashlib
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
UPLOAD_FOLDER_KEY = 'UPLOAD_FOLDER'
PROCESSED_FOLDER_KEY = 'PROCESSED_FOLDER'

DEFAULT_UPLOAD_FOLDER = './uploads'
DEFAULT_PROCESSED_FOLDER = './processed'

PROCESSED_SUFFIX = '.processed'
DOWNLOAD_URL_TEMPLATE = '/download/{filename}'

PLUGIN_FIELD = 'plugin'
FILE_FIELD = 'file'
PLUGIN_ID_FIELD = 'plugin_id'

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = False


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
def _ensure_directories(*paths):
    for path in paths:
        os.makedirs(path, exist_ok=True)


def create_app():
    flask_app = Flask(__name__)
    flask_app.config[UPLOAD_FOLDER_KEY] = DEFAULT_UPLOAD_FOLDER
    flask_app.config[PROCESSED_FOLDER_KEY] = DEFAULT_PROCESSED_FOLDER
    _ensure_directories(
        flask_app.config[UPLOAD_FOLDER_KEY],
        flask_app.config[PROCESSED_FOLDER_KEY],
    )
    return flask_app


app = create_app()


# --------------------------------------------------------------------------- #
# Response helpers
# --------------------------------------------------------------------------- #
def _error_response(message, status_code):
    return (jsonify({'error': message}), status_code)


def _json_response(payload, status_code=HTTP_OK):
    return (jsonify(payload), status_code)


# --------------------------------------------------------------------------- #
# File helpers
# --------------------------------------------------------------------------- #
def _read_binary(filepath):
    with open(filepath, 'rb') as f:
        return f.read()


def _write_binary(filepath, data):
    with open(filepath, 'wb') as f:
        f.write(data)


def _processed_output_path(filepath):
    return os.path.join(
        app.config[PROCESSED_FOLDER_KEY],
        os.path.basename(filepath) + PROCESSED_SUFFIX,
    )


# --------------------------------------------------------------------------- #
# Core processing logic
# --------------------------------------------------------------------------- #
class FileProcessor:

    def __init__(self):
        self.jobs = {}
        self.plugins = {}

    def _generate_job_id(self, filename):
        return hashlib.sha256(filename.encode()).hexdigest()

    @staticmethod
    def _compute_plugin_id(plugin_data):
        return hashlib.md5(plugin_data).hexdigest()

    def load_processing_plugin(self, plugin_data):
        try:
            # SECURITY NOTE: unpickling untrusted data allows arbitrary code
            # execution. Behaviour is preserved here intentionally; plugin
            # uploads should be restricted to trusted sources or replaced with
            # a safe serialization/registration mechanism.
            plugin = pickle.loads(plugin_data)
            plugin_id = self._compute_plugin_id(plugin_data)
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
            file_data = _read_binary(filepath)
            result = plugin.process(file_data)
            output_filename = _processed_output_path(filepath)
            _write_binary(output_filename, result)
            return output_filename
        except Exception as e:
            print(f'File processing failed: {e}')
            return None


processor = FileProcessor()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/upload_plugin', methods=['POST'])
def upload_plugin():
    if PLUGIN_FIELD not in request.files:
        return _error_response('No plugin file provided', HTTP_BAD_REQUEST)
    plugin_file = request.files[PLUGIN_FIELD].read()
    plugin_id = processor.load_processing_plugin(plugin_file)
    if plugin_id:
        return _json_response({'plugin_id': plugin_id}, HTTP_OK)
    return _error_response('Plugin upload failed', HTTP_BAD_REQUEST)


@app.route('/upload_file', methods=['POST'])
def upload_file():
    if FILE_FIELD not in request.files:
        return _error_response('No file provided', HTTP_BAD_REQUEST)
    if PLUGIN_ID_FIELD not in request.form:
        return _error_response('No plugin ID provided', HTTP_BAD_REQUEST)
    file = request.files[FILE_FIELD]
    if file.filename == '':
        return _error_response('Empty filename', HTTP_BAD_REQUEST)
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config[UPLOAD_FOLDER_KEY], filename)
    file.save(filepath)
    processed_file = processor.process_file(filepath, request.form[PLUGIN_ID_FIELD])
    if processed_file:
        processed_name = os.path.basename(processed_file)
        return _json_response(
            {
                'processed_file': processed_name,
                'download_url': DOWNLOAD_URL_TEMPLATE.format(filename=processed_name),
            },
            HTTP_OK,
        )
    return _error_response('File processing failed', HTTP_INTERNAL_ERROR)


@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    filepath = os.path.join(app.config[PROCESSED_FOLDER_KEY], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return _error_response('File not found', HTTP_NOT_FOUND)


@app.route('/status', methods=['GET'])
def status():
    return _json_response(
        {
            'plugins_loaded': len(processor.plugins),
            'jobs_processed': len(processor.jobs),
        },
        HTTP_OK,
    )


def main():
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)


if __name__ == '__main__':
    main()
