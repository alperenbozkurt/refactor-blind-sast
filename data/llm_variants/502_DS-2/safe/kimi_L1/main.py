import hashlib

import yaml
from flask import Flask, jsonify, request

app = Flask(__name__)


class DocumentProcessor:
    """Stores text templates and renders them against supplied documents."""

    def __init__(self):
        self.templates = {}
        self.cached_parsers = {}

    def load_template(self, template_data):
        """Decode and store template bytes, returning their SHA-256 identifier."""
        try:
            template_id = hashlib.sha256(template_data).hexdigest()
            self.templates[template_id] = template_data.decode('utf-8')
            return template_id
        except Exception as e:
            print(f'Template loading failed: {e}')
            return None

    def process_document(self, template_id, document):
        """Render the stored template for template_id with the given document."""
        if template_id not in self.templates:
            return None
        try:
            template = self.templates[template_id]
            result = template.format(document=document)
            return result
        except Exception as e:
            print(f'Document processing failed: {e}')
            return None


processor = DocumentProcessor()


@app.route('/upload_template', methods=['POST'])
def upload_template():
    """Accept a template file upload and return its identifier."""
    if 'template' not in request.files:
        return jsonify({'error': 'No template provided'}), 400

    template_file = request.files['template'].read()
    template_id = processor.load_template(template_file)

    if template_id is None:
        return jsonify({'error': 'Template upload failed'}), 400
    return jsonify({'template_id': template_id}), 200


@app.route('/process', methods=['POST'])
def process():
    """Render a previously uploaded template against a supplied document."""
    data = request.get_json()
    if not data or 'template_id' not in data or 'document' not in data:
        return jsonify({'error': 'Invalid request'}), 400

    result = processor.process_document(data['template_id'], data['document'])

    if result is None:
        return jsonify({'error': 'Processing failed'}), 400
    return jsonify({'result': result}), 200


@app.route('/config', methods=['POST'])
def update_config():
    """Parse a YAML configuration payload from the request body."""
    config_data = request.data
    try:
        config = yaml.safe_load(config_data)
        return jsonify({'status': 'Config updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
