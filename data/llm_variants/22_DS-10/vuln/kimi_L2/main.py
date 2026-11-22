"""Flask service for rendering, listing, and uploading Jinja2 templates."""

import os
from dataclasses import dataclass

from flask import Flask, abort, jsonify, request
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

# --- Application configuration ------------------------------------------------

DEFAULT_TEMPLATE_ROOT = '/var/www/templates'
DEFAULT_MAX_TEMPLATE_SIZE = 1024 * 1024  # 1 MiB

ALLOWED_TEMPLATE_EXTENSIONS = ('.html', '.txt')

# --- Response messages ----------------------------------------------------------

MSG_MISSING_TEMPLATE = 'Missing template parameter'
MSG_RENDER_FAILED = 'Template not found or rendering failed'
MSG_NO_FILE = 'No file uploaded'
MSG_NO_FILENAME = 'No filename provided'
MSG_INVALID_FILE_TYPE = 'Invalid file type'


@dataclass(frozen=True)
class ServerConfig:
    """Settings used when running the development server."""

    host: str = '0.0.0.0'
    port: int = 5000
    debug: bool = True


SERVER_CONFIG = ServerConfig()


def create_app():
    """Create the Flask application and apply the default configuration."""
    app = Flask(__name__)
    app.config['TEMPLATE_ROOT'] = DEFAULT_TEMPLATE_ROOT
    app.config['MAX_TEMPLATE_SIZE'] = DEFAULT_MAX_TEMPLATE_SIZE
    return app


app = create_app()


def is_allowed_template(filename):
    """Return True when *filename* ends with an allowed template extension."""
    return filename.endswith(ALLOWED_TEMPLATE_EXTENSIONS)


def error_response(message, status_code):
    """Build a ``(response, status_code)`` tuple with a JSON error body."""
    return jsonify({'error': message}), status_code


class TemplateRenderer:
    """Validate, render, and enumerate templates from the template root."""

    def __init__(self):
        os.makedirs(app.config['TEMPLATE_ROOT'], exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(app.config['TEMPLATE_ROOT']),
            autoescape=True,
        )

    def validate_template_path(self, template_path):
        full_path = os.path.join(app.config['TEMPLATE_ROOT'], template_path)
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
        templates = []
        for root, _, files in os.walk(app.config['TEMPLATE_ROOT']):
            rel_path = os.path.relpath(root, app.config['TEMPLATE_ROOT'])
            for file in files:
                if is_allowed_template(file):
                    templates.append(os.path.join(rel_path, file))
        return templates


renderer = TemplateRenderer()


@app.route('/render', methods=['POST'])
def render_template_endpoint():
    data = request.get_json()
    if not data or 'template' not in data:
        abort(400, description=MSG_MISSING_TEMPLATE)
    context = data.get('context', {})
    rendered = renderer.render_template(data['template'], context)
    if rendered is not None:
        return jsonify({'status': 'success', 'content': rendered})
    return error_response(MSG_RENDER_FAILED, 404)


@app.route('/templates', methods=['GET'])
def list_templates_endpoint():
    try:
        templates = renderer.list_templates()
        return jsonify({'status': 'success', 'templates': templates})
    except Exception as e:
        return error_response(str(e), 500)


@app.route('/upload', methods=['POST'])
def upload_template():
    if 'file' not in request.files:
        abort(400, description=MSG_NO_FILE)
    file = request.files['file']
    if not file.filename:
        abort(400, description=MSG_NO_FILENAME)
    if not is_allowed_template(file.filename):
        abort(400, description=MSG_INVALID_FILE_TYPE)
    save_path = os.path.join(app.config['TEMPLATE_ROOT'], file.filename)
    try:
        file.save(save_path)
        return jsonify({'status': 'success', 'path': file.filename}), 201
    except Exception as e:
        return error_response(str(e), 500)


if __name__ == '__main__':
    app.run(
        host=SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        debug=SERVER_CONFIG.debug,
    )
