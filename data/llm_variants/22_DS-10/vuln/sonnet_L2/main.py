import os
from flask import Flask, request, jsonify, abort
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

# --------------------------------------------------------------------------- #
# Constants / configuration
# --------------------------------------------------------------------------- #
DEFAULT_TEMPLATE_ROOT = '/var/www/templates'
DEFAULT_MAX_TEMPLATE_SIZE = 1024 * 1024
ALLOWED_TEMPLATE_EXTENSIONS = ('.html', '.txt')

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = True

STATUS_SUCCESS = 'success'
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_CREATED = 201
HTTP_SERVER_ERROR = 500

ERR_MISSING_TEMPLATE = 'Missing template parameter'
ERR_NO_FILE = 'No file uploaded'
ERR_NO_FILENAME = 'No filename provided'
ERR_INVALID_FILE_TYPE = 'Invalid file type'
ERR_RENDER_FAILED = 'Template not found or rendering failed'

app = Flask(__name__)
app.config['TEMPLATE_ROOT'] = DEFAULT_TEMPLATE_ROOT
app.config['MAX_TEMPLATE_SIZE'] = DEFAULT_MAX_TEMPLATE_SIZE


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _template_root():
    """Return the currently configured template root directory."""
    return app.config['TEMPLATE_ROOT']


def _has_allowed_extension(filename):
    """Return True if the filename has an allowed template extension."""
    return filename.endswith(ALLOWED_TEMPLATE_EXTENSIONS)


def _error_response(message, status_code):
    """Build a JSON error response tuple."""
    return (jsonify({'error': message}), status_code)


# --------------------------------------------------------------------------- #
# Rendering service
# --------------------------------------------------------------------------- #
class TemplateRenderer:

    def __init__(self):
        os.makedirs(_template_root(), exist_ok=True)
        self.env = self._build_environment()

    @staticmethod
    def _build_environment():
        return Environment(
            loader=FileSystemLoader(_template_root()),
            autoescape=True,
        )

    def validate_template_path(self, template_path):
        # NOTE: behaviour intentionally preserved; only checks existence.
        full_path = os.path.join(_template_root(), template_path)
        return os.path.exists(full_path)

    def render_template(self, template_path, context=None):
        try:
            if not self.validate_template_path(template_path):
                return None
            template = self.env.get_template(template_path)
            return template.render(**context or {})
        except TemplateNotFound:
            return None
        except Exception as e:
            print(f'Template rendering error: {str(e)}')
            return None

    def list_templates(self):
        root_dir = _template_root()
        templates = []
        for (root, _, files) in os.walk(root_dir):
            rel_path = os.path.relpath(root, root_dir)
            templates.extend(
                os.path.join(rel_path, file)
                for file in files
                if _has_allowed_extension(file)
            )
        return templates


renderer = TemplateRenderer()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/render', methods=['POST'])
def render_template_endpoint():
    data = request.get_json()
    if not data or 'template' not in data:
        abort(HTTP_BAD_REQUEST, description=ERR_MISSING_TEMPLATE)
    context = data.get('context', {})
    rendered = renderer.render_template(data['template'], context)
    if rendered is not None:
        return jsonify({'status': STATUS_SUCCESS, 'content': rendered})
    return _error_response(ERR_RENDER_FAILED, HTTP_NOT_FOUND)


@app.route('/templates', methods=['GET'])
def list_templates_endpoint():
    try:
        templates = renderer.list_templates()
        return jsonify({'status': STATUS_SUCCESS, 'templates': templates})
    except Exception as e:
        return _error_response(str(e), HTTP_SERVER_ERROR)


@app.route('/upload', methods=['POST'])
def upload_template():
    if 'file' not in request.files:
        abort(HTTP_BAD_REQUEST, description=ERR_NO_FILE)
    file = request.files['file']
    if not file.filename:
        abort(HTTP_BAD_REQUEST, description=ERR_NO_FILENAME)
    if not _has_allowed_extension(file.filename):
        abort(HTTP_BAD_REQUEST, description=ERR_INVALID_FILE_TYPE)
    # NOTE: behaviour intentionally preserved; filename is used as provided.
    save_path = os.path.join(_template_root(), file.filename)
    try:
        file.save(save_path)
        return (
            jsonify({'status': STATUS_SUCCESS, 'path': file.filename}),
            HTTP_CREATED,
        )
    except Exception as e:
        return _error_response(str(e), HTTP_SERVER_ERROR)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
