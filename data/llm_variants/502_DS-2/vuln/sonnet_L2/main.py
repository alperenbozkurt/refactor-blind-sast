import yaml
import marshal
import hashlib
from flask import Flask, request, jsonify

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HTTP_OK = 200
HTTP_BAD_REQUEST = 400

TEMPLATE_FIELD = 'template'
TEMPLATE_ID_KEY = 'template_id'
DOCUMENT_KEY = 'document'
RESULT_KEY = 'result'

COMPILE_FILENAME = '<string>'
COMPILE_MODE = 'exec'

ERROR_NO_TEMPLATE = 'No template provided'
ERROR_UPLOAD_FAILED = 'Template upload failed'
ERROR_INVALID_REQUEST = 'Invalid request'
ERROR_PROCESSING_FAILED = 'Processing failed'
STATUS_CONFIG_UPDATED = 'Config updated'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = True

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_response(payload, status):
    """Build a (response, status) tuple as returned by the route handlers."""
    return (jsonify(payload), status)


def _error_response(message, status=HTTP_BAD_REQUEST):
    return _json_response({'error': message}, status)


def _compute_template_id(template_data):
    """Return the content-derived identifier of a serialized template."""
    return hashlib.sha256(template_data).hexdigest()


def _is_valid_process_request(data):
    return bool(data) and TEMPLATE_ID_KEY in data and DOCUMENT_KEY in data


def _parse_config(config_data):
    # SECURITY WARNING: yaml.Loader can construct arbitrary Python objects.
    # Behaviour is preserved here; prefer yaml.safe_load for untrusted input.
    return yaml.load(config_data, Loader=yaml.Loader)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

class DocumentProcessor:
    """Stores templates (marshalled code objects) and runs them on documents.

    SECURITY WARNING: templates are deserialized with ``marshal`` and executed
    with ``exec``. This allows arbitrary code execution and must only be used
    with fully trusted input.
    """

    def __init__(self):
        self.templates = {}
        self.cached_parsers = {}

    def load_template(self, template_data):
        try:
            template = marshal.loads(template_data)
            template_id = _compute_template_id(template_data)
            self.templates[template_id] = template
            return template_id
        except Exception as e:
            print(f'Template loading failed: {e}')
            return None

    def _get_compiled(self, template_id):
        if template_id not in self.cached_parsers:
            code = self.templates[template_id]
            self.cached_parsers[template_id] = compile(
                code, COMPILE_FILENAME, COMPILE_MODE
            )
        return self.cached_parsers[template_id]

    @staticmethod
    def _build_namespace(document):
        return {DOCUMENT_KEY: document, RESULT_KEY: None}

    def process_document(self, template_id, document):
        if template_id not in self.templates:
            return None
        try:
            compiled = self._get_compiled(template_id)
            namespace = self._build_namespace(document)
            exec(compiled, namespace)
            return namespace.get(RESULT_KEY)
        except Exception as e:
            print(f'Document processing failed: {e}')
            return None


processor = DocumentProcessor()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/upload_template', methods=['POST'])
def upload_template():
    if TEMPLATE_FIELD not in request.files:
        return _error_response(ERROR_NO_TEMPLATE)
    template_file = request.files[TEMPLATE_FIELD].read()
    template_id = processor.load_template(template_file)
    if template_id:
        return _json_response({TEMPLATE_ID_KEY: template_id}, HTTP_OK)
    return _error_response(ERROR_UPLOAD_FAILED)


@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    if not _is_valid_process_request(data):
        return _error_response(ERROR_INVALID_REQUEST)
    result = processor.process_document(data[TEMPLATE_ID_KEY], data[DOCUMENT_KEY])
    if result is not None:
        return _json_response({RESULT_KEY: result}, HTTP_OK)
    return _error_response(ERROR_PROCESSING_FAILED)


@app.route('/config', methods=['POST'])
def update_config():
    config_data = request.data
    try:
        config = _parse_config(config_data)
        return _json_response({'status': STATUS_CONFIG_UPDATED}, HTTP_OK)
    except Exception as e:
        return _error_response(str(e))


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
