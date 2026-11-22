import os

from flask import Flask, abort, jsonify, request
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['TEMPLATE_ROOT'] = os.path.abspath('/var/www/templates')
app.config['MAX_TEMPLATE_SIZE'] = 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'.html', '.txt'}


class TemplateRenderer:
    """Renders, lists and validates templates stored under TEMPLATE_ROOT."""

    def __init__(self):
        os.makedirs(app.config['TEMPLATE_ROOT'], exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(app.config['TEMPLATE_ROOT']),
            autoescape=True,
            auto_reload=False,
        )

    def is_safe_path(self, path):
        """Return True if `path` resolves to a location inside TEMPLATE_ROOT."""
        base_path = os.path.abspath(app.config['TEMPLATE_ROOT'])
        requested_path = os.path.abspath(os.path.join(base_path, path))
        return requested_path.startswith(base_path + os.sep)

    def is_allowed_template(self, filename):
        """Return True if `filename` has an allowed extension and no traversal markers."""
        if not filename:
            return False
        if not any(filename.endswith(ext) for ext in app.config['ALLOWED_EXTENSIONS']):
            return False
        return '../' not in filename and '~' not in filename

    def render_template(self, template_path, context=None):
        """Render `template_path` with `context`, returning None on any failure."""
        try:
            if not isinstance(template_path, str) or not self.is_allowed_template(template_path):
                return None
            if not self.is_safe_path(template_path):
                return None

            safe_context = {}
            if context and isinstance(context, dict):
                safe_context = {
                    key: value if isinstance(value, str) else str(value)
                    for key, value in context.items()
                }

            template = self.env.get_template(template_path)
            return template.render(**safe_context)
        except TemplateNotFound:
            return None
        except Exception as e:
            app.logger.error(f'Template rendering error: {e}')
            return None

    def list_templates(self):
        """Return the relative paths of all allowed templates under TEMPLATE_ROOT."""
        templates = []
        try:
            for root, _, files in os.walk(app.config['TEMPLATE_ROOT']):
                rel_path = os.path.relpath(root, app.config['TEMPLATE_ROOT'])
                for filename in files:
                    file_path = os.path.join(rel_path, filename)
                    if self.is_allowed_template(filename) and self.is_safe_path(file_path):
                        templates.append(file_path)
            return templates
        except Exception as e:
            app.logger.error(f'Error listing templates: {e}')
            return []


renderer = TemplateRenderer()


@app.route('/render', methods=['POST'])
def render_template_endpoint():
    data = request.get_json()
    if not data or 'template' not in data:
        abort(400, description='Invalid request')
    if not isinstance(data.get('template'), str):
        abort(400, description='Invalid template parameter')

    context = data.get('context', {})
    if not isinstance(context, dict):
        abort(400, description='Invalid context parameter')

    rendered = renderer.render_template(data['template'], context)
    if rendered is not None:
        return jsonify({'status': 'success', 'content': rendered})
    return jsonify({'error': 'Template rendering failed'}), 404


@app.route('/templates', methods=['GET'])
def list_templates_endpoint():
    try:
        templates = renderer.list_templates()
        return jsonify({'status': 'success', 'templates': templates})
    except Exception as e:
        app.logger.error(f'Error listing templates: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/upload', methods=['POST'])
def upload_template():
    if 'file' not in request.files:
        abort(400, description='Invalid request')

    file = request.files['file']
    if not file.filename:
        abort(400, description='No filename provided')
    if not renderer.is_allowed_template(file.filename):
        abort(400, description='Invalid file type')

    safe_filename = secure_filename(file.filename)
    if not renderer.is_safe_path(safe_filename):
        abort(400, description='Invalid file path')

    save_path = os.path.join(app.config['TEMPLATE_ROOT'], safe_filename)
    try:
        file.save(save_path)
        return jsonify({'status': 'success', 'path': safe_filename}), 201
    except Exception as e:
        app.logger.error(f'File upload error: {e}')
        return jsonify({'error': 'File upload failed'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
