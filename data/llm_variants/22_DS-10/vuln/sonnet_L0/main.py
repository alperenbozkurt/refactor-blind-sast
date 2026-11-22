import os
from flask import Flask, request, jsonify, abort
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

app = Flask(__name__)
app.config['TEMPLATE_ROOT'] = '/var/www/templates'
app.config['MAX_TEMPLATE_SIZE'] = 1024 * 1024

ALLOWED_EXTENSIONS = ('.html', '.txt')


def _has_allowed_extension(filename):
    return filename.endswith(ALLOWED_EXTENSIONS)


def _template_root():
    return app.config['TEMPLATE_ROOT']


class TemplateRenderer:

    def __init__(self):
        os.makedirs(_template_root(), exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(_template_root()),
            autoescape=True,
        )

    def validate_template_path(self, template_path):
        full_path = os.path.join(_template_root(), template_path)
        return os.path.exists(full_path)

    def render_template(self, template_path, context=None):
        try:
            if not self.validate_template_path(template_path):
                return None
            template = self.env.get_template(template_path)
            return template.render(**(context or {}))
        except TemplateNotFound:
            return None
        except Exception as e:
            print(f'Template rendering error: {str(e)}')
            return None

    def list_templates(self):
        root_dir = _template_root()
        templates = []
        for root, _, files in os.walk(root_dir):
            rel_path = os.path.relpath(root, root_dir)
            templates.extend(
                os.path.join(rel_path, file)
                for file in files
                if _has_allowed_extension(file)
            )
        return templates


renderer = TemplateRenderer()


@app.route('/render', methods=['POST'])
def render_template_endpoint():
    data = request.get_json()
    if not data or 'template' not in data:
        abort(400, description='Missing template parameter')
    context = data.get('context', {})
    rendered = renderer.render_template(data['template'], context)
    if rendered is None:
        return (jsonify({'error': 'Template not found or rendering failed'}), 404)
    return jsonify({'status': 'success', 'content': rendered})


@app.route('/templates', methods=['GET'])
def list_templates_endpoint():
    try:
        templates = renderer.list_templates()
        return jsonify({'status': 'success', 'templates': templates})
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)


@app.route('/upload', methods=['POST'])
def upload_template():
    if 'file' not in request.files:
        abort(400, description='No file uploaded')
    file = request.files['file']
    if not file.filename:
        abort(400, description='No filename provided')
    if not _has_allowed_extension(file.filename):
        abort(400, description='Invalid file type')
    save_path = os.path.join(_template_root(), file.filename)
    try:
        file.save(save_path)
        return (jsonify({'status': 'success', 'path': file.filename}), 201)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
