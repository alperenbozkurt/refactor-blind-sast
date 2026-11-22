import yaml
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
HTTP_OK = 200
HTTP_BAD_REQUEST = 400

TEMPLATE_FILE_FIELD = 'template'
TEMPLATE_ID_FIELD = 'template_id'
DOCUMENT_FIELD = 'document'

TEMPLATE_ENCODING = 'utf-8'

MSG_NO_TEMPLATE = 'No template provided'
MSG_TEMPLATE_UPLOAD_FAILED = 'Template upload failed'
MSG_INVALID_REQUEST = 'Invalid request'
MSG_PROCESSING_FAILED = 'Processing failed'
MSG_CONFIG_UPDATED = 'Config updated'

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 5000


class ServerConfig:
    """Network settings used when running the development server."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _compute_template_id(template_data):
    """Return the content-derived identifier for a template."""
    return hashlib.sha256(template_data).hexdigest()


def _decode_template(template_data):
    """Decode raw template bytes into text."""
    return template_data.decode(TEMPLATE_ENCODING)


def _render_template(template, document):
    """Render a template string with the supplied document."""
    return template.format(document=document)


def _json_response(payload, status=HTTP_OK):
    return (jsonify(payload), status)


def _error_response(message, status=HTTP_BAD_REQUEST):
    return _json_response({'error': message}, status)


def _is_valid_process_request(data):
    return bool(data) and TEMPLATE_ID_FIELD in data and DOCUMENT_FIELD in data


# --------------------------------------------------------------------------- #
# Core logic
# --------------------------------------------------------------------------- #
class DocumentProcessor:

    def __init__(self):
        self.templates = {}
        self.cached_parsers = {}

    def load_template(self, template_data):
        try:
            template_id = _compute_template_id(template_data)
            self.templates[template_id] = _decode_template(template_data)
            return template_id
        except Exception as e:
            print(f'Template loading failed: {e}')
            return None

    def process_document(self, template_id, document):
        if template_id not in self.templates:
            return None
        try:
            template = self.templates[template_id]
            return _render_template(template, document)
        except Exception as e:
            print(f'Document processing failed: {e}')
            return None


processor = DocumentProcessor()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/upload_template', methods=['POST'])
def upload_template():
    if TEMPLATE_FILE_FIELD not in request.files:
        return _error_response(MSG_NO_TEMPLATE)
    template_file = request.files[TEMPLATE_FILE_FIELD].read()
    template_id = processor.load_template(template_file)
    if template_id:
        return _json_response({TEMPLATE_ID_FIELD: template_id}, HTTP_OK)
    return _error_response(MSG_TEMPLATE_UPLOAD_FAILED)


@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    if not _is_valid_process_request(data):
        return _error_response(MSG_INVALID_REQUEST)
    result = processor.process_document(data[TEMPLATE_ID_FIELD], data[DOCUMENT_FIELD])
    if result is not None:
        return _json_response({'result': result}, HTTP_OK)
    return _error_response(MSG_PROCESSING_FAILED)


@app.route('/config', methods=['POST'])
def update_config():
    config_data = request.data
    try:
        config = yaml.safe_load(config_data)
        return _json_response({'status': MSG_CONFIG_UPDATED}, HTTP_OK)
    except Exception as e:
        return _error_response(str(e))


if __name__ == '__main__':
    server_config = ServerConfig()
    app.run(host=server_config.host, port=server_config.port)
