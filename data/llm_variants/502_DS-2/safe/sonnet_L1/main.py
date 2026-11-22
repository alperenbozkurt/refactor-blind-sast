import yaml
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)


class DocumentProcessor:
    """Stores templates by content hash and renders documents with them."""

    def __init__(self):
        self.templates = {}
        self.cached_parsers = {}

    def load_template(self, template_data):
        """Store a template and return its SHA-256 id, or None on failure."""
        try:
            template_id = hashlib.sha256(template_data).hexdigest()
            self.templates[template_id] = template_data.decode('utf-8')
            return template_id
        except Exception as e:
            print(f'Template loading failed: {e}')
            return None

    def process_document(self, template_id, document):
        """Render a document with the given template, or return None on failure."""
        if template_id not in self.templates:
            return None

        try:
            template = self.templates[template_id]
            return template.format(document=document)
        except Exception as e:
            print(f'Document processing failed: {e}')
            return None


processor = DocumentProcessor()


def _error_response(message, status_code=400):
    """Build a JSON error response."""
    return jsonify({'error': message}), status_code


def _success_response(payload):
    """Build a JSON 200 response."""
    return jsonify(payload), 200


@app.route('/upload_template', methods=['POST'])
def upload_template():
    if 'template' not in request.files:
        return _error_response('No template provided')

    template_file = request.files['template'].read()
    template_id = processor.load_template(template_file)

    if template_id:
        return _success_response({'template_id': template_id})
    return _error_response('Template upload failed')


@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    if not data or 'template_id' not in data or 'document' not in data:
        return _error_response('Invalid request')

    result = processor.process_document(data['template_id'], data['document'])

    if result is not None:
        return _success_response({'result': result})
    return _error_response('Processing failed')


@app.route('/config', methods=['POST'])
def update_config():
    config_data = request.data
    try:
        yaml.safe_load(config_data)
        return _success_response({'status': 'Config updated'})
    except Exception as e:
        return _error_response(str(e))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
