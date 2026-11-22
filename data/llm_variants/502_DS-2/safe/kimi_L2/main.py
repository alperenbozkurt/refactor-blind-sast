"""Flask service for uploading templates and processing documents."""

import hashlib
from dataclasses import dataclass

import yaml
from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServerConfig:
    """Network settings used when running the development server."""

    host: str = '0.0.0.0'
    port: int = 5000


SERVER_CONFIG = ServerConfig()

# HTTP status codes
HTTP_OK = 200
HTTP_BAD_REQUEST = 400

# Request/response field names
TEMPLATE_FILE_FIELD = 'template'
TEMPLATE_ID_FIELD = 'template_id'
DOCUMENT_FIELD = 'document'
RESULT_FIELD = 'result'
ERROR_FIELD = 'error'
STATUS_FIELD = 'status'

# Response messages
MSG_NO_TEMPLATE_PROVIDED = 'No template provided'
MSG_TEMPLATE_UPLOAD_FAILED = 'Template upload failed'
MSG_INVALID_REQUEST = 'Invalid request'
MSG_PROCESSING_FAILED = 'Processing failed'
MSG_CONFIG_UPDATED = 'Config updated'

# Template storage encoding
TEMPLATE_ENCODING = 'utf-8'

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _error_response(message, status_code=HTTP_BAD_REQUEST):
    """Build a JSON error response tuple."""
    return jsonify({ERROR_FIELD: message}), status_code


def _is_valid_process_request(data):
    """Check that the JSON body contains all required fields."""
    return bool(data) and TEMPLATE_ID_FIELD in data and DOCUMENT_FIELD in data


def _parse_config(config_data):
    """Parse raw YAML configuration data."""
    return yaml.safe_load(config_data)


# ---------------------------------------------------------------------------
# Document processing
# ---------------------------------------------------------------------------


class DocumentProcessor:
    """Stores document templates and renders documents against them."""

    def __init__(self):
        self.templates = {}
        self.cached_parsers = {}

    def load_template(self, template_data):
        try:
            template_id = self._compute_template_id(template_data)
            self.templates[template_id] = self._decode_template(template_data)
            return template_id
        except Exception as e:
            print(f'Template loading failed: {e}')
            return None

    def process_document(self, template_id, document):
        if template_id not in self.templates:
            return None
        try:
            template = self.templates[template_id]
            return self._render_document(template, document)
        except Exception as e:
            print(f'Document processing failed: {e}')
            return None

    @staticmethod
    def _compute_template_id(template_data):
        return hashlib.sha256(template_data).hexdigest()

    @staticmethod
    def _decode_template(template_data):
        return template_data.decode(TEMPLATE_ENCODING)

    @staticmethod
    def _render_document(template, document):
        return template.format(document=document)


processor = DocumentProcessor()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route('/upload_template', methods=['POST'])
def upload_template():
    if TEMPLATE_FILE_FIELD not in request.files:
        return _error_response(MSG_NO_TEMPLATE_PROVIDED)
    template_data = request.files[TEMPLATE_FILE_FIELD].read()
    template_id = processor.load_template(template_data)
    if template_id:
        return jsonify({TEMPLATE_ID_FIELD: template_id}), HTTP_OK
    return _error_response(MSG_TEMPLATE_UPLOAD_FAILED)


@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    if not _is_valid_process_request(data):
        return _error_response(MSG_INVALID_REQUEST)
    result = processor.process_document(data[TEMPLATE_ID_FIELD], data[DOCUMENT_FIELD])
    if result is not None:
        return jsonify({RESULT_FIELD: result}), HTTP_OK
    return _error_response(MSG_PROCESSING_FAILED)


@app.route('/config', methods=['POST'])
def update_config():
    try:
        _parse_config(request.data)
        return jsonify({STATUS_FIELD: MSG_CONFIG_UPDATED}), HTTP_OK
    except Exception as e:
        return _error_response(str(e))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    app.run(host=SERVER_CONFIG.host, port=SERVER_CONFIG.port)


if __name__ == '__main__':
    main()
