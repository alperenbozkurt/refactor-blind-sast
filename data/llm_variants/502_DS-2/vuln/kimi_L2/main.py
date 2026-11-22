"""Document processing web service.

Refactored for a larger codebase: configuration lives in ``ServerConfig``
and named constants, shared response construction is centralised in small
helpers, and ``DocumentProcessor`` is decomposed into single-purpose
methods. All routes, signatures, and runtime behaviour are unchanged.

NOTE: This service executes uploaded, unmarshalled template code and uses
``yaml.Loader`` on request bodies; it must only ever handle fully trusted
input.
"""

import hashlib
import marshal
from dataclasses import dataclass

import yaml
from flask import Flask, jsonify, request


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServerConfig:
    """Runtime configuration for the Flask development server."""

    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = True


SERVER_CONFIG = ServerConfig()

# Route paths.
ROUTE_UPLOAD_TEMPLATE = '/upload_template'
ROUTE_PROCESS = '/process'
ROUTE_CONFIG = '/config'

# Request field names.
TEMPLATE_FILE_FIELD = 'template'
TEMPLATE_ID_FIELD = 'template_id'
DOCUMENT_FIELD = 'document'

# Response payload keys.
ERROR_KEY = 'error'
RESULT_KEY = 'result'
STATUS_KEY = 'status'

# Response messages.
MSG_NO_TEMPLATE_PROVIDED = 'No template provided'
MSG_TEMPLATE_UPLOAD_FAILED = 'Template upload failed'
MSG_INVALID_REQUEST = 'Invalid request'
MSG_PROCESSING_FAILED = 'Processing failed'
MSG_CONFIG_UPDATED = 'Config updated'

# HTTP status codes.
HTTP_OK = 200
HTTP_BAD_REQUEST = 400

# Template compilation settings.
COMPILE_FILENAME = '<string>'
COMPILE_MODE = 'exec'

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _json_response(payload, status_code):
    """Build a Flask ``(response, status_code)`` tuple for *payload*."""
    return (jsonify(payload), status_code)


def _error_response(message, status_code=HTTP_BAD_REQUEST):
    """Build a standard JSON error response tuple."""
    return _json_response({ERROR_KEY: message}, status_code)


def _parse_config(config_data):
    """Deserialize a raw YAML configuration payload."""
    return yaml.load(config_data, Loader=yaml.Loader)


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

class DocumentProcessor:
    """Loads document templates and executes them against documents."""

    def __init__(self):
        self.templates = {}
        self.cached_parsers = {}

    # -- internal helpers --------------------------------------------------

    @staticmethod
    def _template_id_for(template_data):
        """Return the SHA-256 hex digest used as the template identifier."""
        return hashlib.sha256(template_data).hexdigest()

    def _parser_for(self, template_id):
        """Return the compiled parser for *template_id*.

        The template source is compiled on first use and the resulting code
        object is cached for subsequent calls.
        """
        if template_id not in self.cached_parsers:
            self.cached_parsers[template_id] = compile(
                self.templates[template_id], COMPILE_FILENAME, COMPILE_MODE
            )
        return self.cached_parsers[template_id]

    @staticmethod
    def _execute(parser, document):
        """Run *parser* against *document* and return its ``result`` value."""
        namespace = {'document': document, 'result': None}
        exec(parser, namespace)
        return namespace.get('result')

    # -- public API --------------------------------------------------------

    def load_template(self, template_data):
        try:
            template = marshal.loads(template_data)
            template_id = self._template_id_for(template_data)
            self.templates[template_id] = template
            return template_id
        except Exception as e:
            print(f'Template loading failed: {e}')
            return None

    def process_document(self, template_id, document):
        if template_id not in self.templates:
            return None
        try:
            parser = self._parser_for(template_id)
            return self._execute(parser, document)
        except Exception as e:
            print(f'Document processing failed: {e}')
            return None


processor = DocumentProcessor()


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

@app.route(ROUTE_UPLOAD_TEMPLATE, methods=['POST'])
def upload_template():
    if TEMPLATE_FILE_FIELD not in request.files:
        return _error_response(MSG_NO_TEMPLATE_PROVIDED)
    template_data = request.files[TEMPLATE_FILE_FIELD].read()
    template_id = processor.load_template(template_data)
    if template_id:
        return _json_response({TEMPLATE_ID_FIELD: template_id}, HTTP_OK)
    return _error_response(MSG_TEMPLATE_UPLOAD_FAILED)


@app.route(ROUTE_PROCESS, methods=['POST'])
def process():
    data = request.get_json()
    if not data or TEMPLATE_ID_FIELD not in data or DOCUMENT_FIELD not in data:
        return _error_response(MSG_INVALID_REQUEST)
    result = processor.process_document(
        data[TEMPLATE_ID_FIELD], data[DOCUMENT_FIELD]
    )
    if result is not None:
        return _json_response({RESULT_KEY: result}, HTTP_OK)
    return _error_response(MSG_PROCESSING_FAILED)


@app.route(ROUTE_CONFIG, methods=['POST'])
def update_config():
    config_data = request.data
    try:
        config = _parse_config(config_data)
        return _json_response({STATUS_KEY: MSG_CONFIG_UPDATED}, HTTP_OK)
    except Exception as e:
        return _error_response(str(e))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Start the Flask development server with the configured settings."""
    app.run(
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug,
    )


if __name__ == '__main__':
    main()
