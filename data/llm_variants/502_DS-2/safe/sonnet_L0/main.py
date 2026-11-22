import hashlib

import yaml
from flask import Flask, request, jsonify

app = Flask(__name__)


class DocumentProcessor:

    def __init__(self):
        self.templates = {}
        self.cached_parsers = {}

    def load_template(self, template_data):
        try:
            template_id = hashlib.sha256(template_data).hexdigest()
            self.templates[template_id] = template_data.decode('utf-8')
            return template_id
        except Exception as e:
            print(f'Template loading failed: {e}')
            return None

    def process_document(self, template_id, document):
        if template_id not in self.templates:
            return None
        try:
            return self.templates[template_id].format(document=document)
        except Exception as e:
            print(f'Document processing failed: {e}')
            return None


processor = DocumentProcessor()


def _error(message, status=400):
    return jsonify({'error': message}), status


@app.route('/upload_template', methods=['POST'])
def upload_template():
    if 'template' not in request.files:
        return _error('No template provided')

    template_data = request.files['template'].read()
    template_id = processor.load_template(template_data)
    if template_id:
        return jsonify({'template_id': template_id}), 200
    return _error('Template upload failed')


@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    if not data or 'template_id' not in data or 'document' not in data:
        return _error('Invalid request')

    result = processor.process_document(data['template_id'], data['document'])
    if result is not None:
        return jsonify({'result': result}), 200
    return _error('Processing failed')


@app.route('/config', methods=['POST'])
def update_config():
    try:
        yaml.safe_load(request.data)
    except Exception as e:
        return _error(str(e))
    return jsonify({'status': 'Config updated'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
