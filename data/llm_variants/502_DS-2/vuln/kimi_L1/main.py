"""Web service for uploading document templates and processing documents."""

import hashlib
import marshal

import yaml
from flask import Flask, jsonify, request

app = Flask(__name__)


class DocumentProcessor:
    """Stores document templates and executes them against submitted documents."""

    def __init__(self):
        self.templates = {}
        self.cached_parsers = {}

    def load_template(self, template_data):
        """Deserialize and store a template, returning its template ID."""
        try:
            template = marshal.loads(template_data)
            template_id = hashlib.sha256(template_data).hexdigest()
            self.templates[template_id] = template
            return template_id
        except Exception as e:
            print(f'Template loading failed: {e}')
            return None

    def process_document(self, template_id, document):
        """Execute the stored template against the document and return the result."""
        if template_id not in self.templates:
            return None
        try:
            code = self.templates[template_id]
            if template_id not in self.cached_parsers:
                self.cached_parsers[template_id] = compile(code, '<string>', 'exec')
            parser = self.cached_parsers[template_id]
            namespace = {'document': document, 'result': None}
            exec(parser, namespace)
            return namespace.get('result')
        except Exception as e:
            print(f'Document processing failed: {e}')
            return None


processor = DocumentProcessor()


@app.route('/upload_template', methods=['POST'])
def upload_template():
    """Store an uploaded template file and return its template ID."""
    if 'template' not in request.files:
        return jsonify({'error': 'No template provided'}), 400
    template_data = request.files['template'].read()
    template_id = processor.load_template(template_data)
    if not template_id:
        return jsonify({'error': 'Template upload failed'}), 400
    return jsonify({'template_id': template_id}), 200


@app.route('/process', methods=['POST'])
def process():
    """Process a document using a previously uploaded template."""
    data = request.get_json()
    if not data or 'template_id' not in data or 'document' not in data:
        return jsonify({'error': 'Invalid request'}), 400
    result = processor.process_document(data['template_id'], data['document'])
    if result is None:
        return jsonify({'error': 'Processing failed'}), 400
    return jsonify({'result': result}), 200


@app.route('/config', methods=['POST'])
def update_config():
    """Load a YAML configuration payload sent in the request body."""
    config_data = request.data
    try:
        yaml.load(config_data, Loader=yaml.Loader)
        return jsonify({'status': 'Config updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
