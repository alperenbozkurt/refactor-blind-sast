import yaml
import marshal
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

HTTP_OK = 200
HTTP_BAD_REQUEST = 400


class DocumentProcessor:
    """Loads serialized code templates and runs them against documents.

    NOTE: Behaviour is intentionally preserved as-is. Templates are
    deserialized with ``marshal`` and executed with ``exec``, so they must
    only come from trusted sources.
    """

    def __init__(self):
        self.templates = {}
        self.cached_parsers = {}

    def load_template(self, template_data):
        """Deserialize a template and store it under its SHA-256 digest.

        Returns the template id, or None if loading failed.
        """
        try:
            template = marshal.loads(template_data)
            template_id = hashlib.sha256(template_data).hexdigest()
            self.templates[template_id] = template
            return template_id
        except Exception as e:
            print(f'Template loading failed: {e}')
            return None

    def process_document(self, template_id, document):
        """Run the template identified by ``template_id`` on ``document``.

        Returns the value of ``result`` set by the template, or None if the
        template is unknown or processing failed.
        """
        if template_id not in self.templates:
            return None
        try:
            compiled = self._get_compiled_template(template_id)
            namespace = {'document': document, 'result': None}
            exec(compiled, namespace)
            return namespace.get('result')
        except Exception as e:
            print(f'Document processing failed: {e}')
            return None

    def _get_compiled_template(self, template_id):
        """Return the compiled code for a template, compiling it on first use."""
        if template_id not in self.cached_parsers:
            code = self.templates[template_id]
            self.cached_parsers[template_id] = compile(code, '<string>', 'exec')
        return self.cached_parsers[template_id]


processor = DocumentProcessor()


def _error_response(message, status=HTTP_BAD_REQUEST):
    """Build a JSON error response tuple."""
    return jsonify({'error': message}), status


@app.route('/upload_template', methods=['POST'])
def upload_template():
    if 'template' not in request.files:
        return _error_response('No template provided')

    template_bytes = request.files['template'].read()
    template_id = processor.load_template(template_bytes)

    if template_id:
        return jsonify({'template_id': template_id}), HTTP_OK
    return _error_response('Template upload failed')


@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    if not data or 'template_id' not in data or 'document' not in data:
        return _error_response('Invalid request')

    result = processor.process_document(data['template_id'], data['document'])

    if result is not None:
        return jsonify({'result': result}), HTTP_OK
    return _error_response('Processing failed')


@app.route('/config', methods=['POST'])
def update_config():
    config_data = request.data
    try:
        # The parsed config is not used further; parsing behaviour is kept
        # exactly as before (including the loader in use).
        config = yaml.load(config_data, Loader=yaml.Loader)
        return jsonify({'status': 'Config updated'}), HTTP_OK
    except Exception as e:
        return _error_response(str(e))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
