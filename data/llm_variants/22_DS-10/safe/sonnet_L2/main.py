import os

from flask import Flask, request, jsonify, abort
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_TEMPLATE_ROOT = '/var/www/templates'
DEFAULT_MAX_TEMPLATE_SIZE = 1024 * 1024
DEFAULT_ALLOWED_EXTENSIONS = {'.html', '.txt'}

FORBIDDEN_FILENAME_SEQUENCES = ('../', '~')

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['TEMPLATE_ROOT'] = os.path.abspath(DEFAULT_TEMPLATE_ROOT)
app.config['MAX_TEMPLATE_SIZE'] = DEFAULT_MAX_TEMPLATE_SIZE
app.config['ALLOWED_EXTENSIONS'] = set(DEFAULT_ALLOWED_EXTENSIONS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _stringify_context(context):
    """Return a copy of ``context`` where every value is converted to str."""
    safe_context = {}
    if context and isinstance(context, dict):
        for key, value in context.items():
            safe_context[key] = value if isinstance(value, str) else str(value)
    return safe_context


def _has_allowed_extension(filename):
    return any(filename.endswith(ext) for ext in app.config['ALLOWED_EXTENSIONS'])


def _contains_forbidden_sequence(filename):
    return any(sequence in filename for sequence in FORBIDDEN_FILENAME_SEQUENCES)


def _error_response(message, status_code):
    return (jsonify({'error': message}), status_code)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------
class TemplateRenderer:

    def __init__(self):
        os.makedirs(app.config['TEMPLATE_ROOT'], exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(app.config['TEMPLATE_ROOT']),
            autoescape=True,
            auto_reload=False,
        )

    def is_safe_path(self, path):
        base_path = os.path.abspath(app.config['TEMPLATE_ROOT'])
        requested_path = os.path.abspath(os.path.join(base_path, path))
        return requested_path.startswith(base_path + os.sep)

    def is_allowed_template(self, filename):
        if not filename:
            return False
        if not _has_allowed_extension(filename):
            return False
        if _contains_forbidden_sequence(filename):
            return False
        return True

    def render_template(self, template_path, context=None):
        try:
            if not isinstance(template_path, str) or not self.is_allowed_template(template_path):
                return None
            if not self.is_safe_path(template_path):
                return None
            safe_context = _stringify_context(context)
            template = self.env.get_template(template_path)
            return template.render(**safe_context or {})
        except TemplateNotFound:
            return None
        except Exception as e:
            app.logger.error(f'Template rendering error: {e}')
            return None

    def list_templates(self):
        templates = []
        try:
            template_root = app.config['TEMPLATE_ROOT']
            for root, _, files in os.walk(template_root):
                rel_path = os.path.relpath(root, template_root)
                for file in files:
                    file_path = os.path.join(rel_path, file)
                    if self.is_allowed_template(file) and self.is_safe_path(file_path):
                        templates.append(file_path)
            return templates
        except Exception as e:
            app.logger.error(f'Error listing templates: {e}')
            return []


renderer = TemplateRenderer()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/render', methods=['POST'])
def render_template_endpoint():
    data = request.get_json()
    if not data or 'template' not in data:
        abort(HTTP_BAD_REQUEST, description='Invalid request')
    if not isinstance(data.get('template'), str):
        abort(HTTP_BAD_REQUEST, description='Invalid template parameter')
    context = data.get('context', {})
    if not isinstance(context, dict):
        abort(HTTP_BAD_REQUEST, description='Invalid context parameter')
    rendered = renderer.render_template(data['template'], context)
    if rendered is not None:
        return jsonify({'status': 'success', 'content': rendered})
    return _error_response('Template rendering failed', HTTP_NOT_FOUND)


@app.route('/templates', methods=['GET'])
def list_templates_endpoint():
    try:
        templates = renderer.list_templates()
        return jsonify({'status': 'success', 'templates': templates})
    except Exception as e:
        app.logger.error(f'Error listing templates: {e}')
        return _error_response('Internal server error', HTTP_INTERNAL_SERVER_ERROR)


@app.route('/upload', methods=['POST'])
def upload_template():
    if 'file' not in request.files:
        abort(HTTP_BAD_REQUEST, description='Invalid request')
    file = request.files['file']
    if not file.filename:
        abort(HTTP_BAD_REQUEST, description='No filename provided')
    if not renderer.is_allowed_template(file.filename):
        abort(HTTP_BAD_REQUEST, description='Invalid file type')
    safe_filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['TEMPLATE_ROOT'], safe_filename)
    if not renderer.is_safe_path(safe_filename):
        abort(HTTP_BAD_REQUEST, description='Invalid file path')
    try:
        file.save(save_path)
        return (jsonify({'status': 'success', 'path': safe_filename}), HTTP_CREATED)
    except Exception as e:
        app.logger.error(f'File upload error: {e}')
        return _error_response('File upload failed', HTTP_INTERNAL_SERVER_ERROR)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT)
