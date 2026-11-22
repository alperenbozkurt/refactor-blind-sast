import hashlib
import marshal

import yaml
from flask import Flask, jsonify, request

app = Flask(__name__)

# SECURITY NOTE: this module deserializes and executes untrusted input
# (marshal.loads, compile/exec, yaml.Loader) and runs Flask with debug=True on
# 0.0.0.0. That is remote code execution by design. The behaviour is kept
# unchanged here, but it should not be exposed to untrusted clients.


class DocumentProcessor:

    def __init__(self):
        self.templates = {}
        self.cached_parsers = {}

    def load_template(self, template_data):
        try:
            template = marshal.loads(template_data)
            template_id = hashlib.sha256(template_data).hexdigest()
            self.templates[template_id] = template
            return template_id
        except Exception as e:
            print(f'Template loading failed: {e}')
            return None

    def _get_parser(self, template_id):
        parser = self.cached_parsers.get(template_id)
        if template_id not in self.cached_parsers:
            parser = compile(self.templates[template_id], '<string>', 'exec')
            self.cached_parsers[template_id] = parser
        return parser

    def process_document(self, template_id, document):
        if template_id not in self.templates:
            return None
        try:
            parser = self._get_parser(template_id)
            namespace = {'document': document, 'result': None}
            exec(parser, namespace)
            return namespace.get('result')
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
    if not template_id:
        return _error('Template upload failed')

    return jsonify({'template_id': template_id}), 200


@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    if not data or 'template_id' not in data or 'document' not in data:
        return _error('Invalid request')

    result = processor.process_document(data['template_id'], data['document'])
    if result is None:
        return _error('Processing failed')

    return jsonify({'result': result}), 200


@app.route('/config', methods=['POST'])
def update_config():
    try:
        yaml.load(request.data, Loader=yaml.Loader)
    except Exception as e:
        return _error(str(e))
    return jsonify({'status': 'Config updated'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
