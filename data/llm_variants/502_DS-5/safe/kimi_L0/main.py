import hashlib
import importlib.util
import json
import os
import shutil
import tempfile

from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['PROCESSED_FOLDER'] = './processed'
app.config['PLUGIN_FOLDER'] = './plugins'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)
os.makedirs(app.config['PLUGIN_FOLDER'], exist_ok=True)


class FileProcessor:

    def __init__(self):
        self.jobs = {}
        self.plugins = {}
        self.allowed_plugin_methods = ['process']

    def _generate_job_id(self, filename):
        return hashlib.sha256(filename.encode()).hexdigest()

    @staticmethod
    def _load_plugin_module(plugin_path):
        spec = importlib.util.spec_from_file_location('plugin_module', plugin_path)
        plugin_module = importlib.util.module_from_spec(spec)
        plugin_module.__dict__['__builtins__'] = {'str': str, 'bytes': bytes, 'len': len, 'int': int, 'range': range}
        spec.loader.exec_module(plugin_module)
        return plugin_module

    def load_processing_plugin(self, plugin_file):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = os.path.join(temp_dir, 'plugin.py')
                plugin_file.save(temp_path)
                plugin_module = self._load_plugin_module(temp_path)
                if not all(hasattr(plugin_module, method) for method in self.allowed_plugin_methods):
                    raise ValueError('Plugin missing required methods')
                with open(temp_path, 'rb') as f:
                    plugin_id = hashlib.md5(f.read()).hexdigest()
                final_path = os.path.join(app.config['PLUGIN_FOLDER'], f'{plugin_id}.py')
                shutil.move(temp_path, final_path)
                self.plugins[plugin_id] = final_path
                return plugin_id
        except Exception as e:
            print(f'Plugin loading failed: {e}')
            return None

    def process_file(self, filepath, plugin_id):
        if plugin_id not in self.plugins:
            return None
        try:
            plugin_module = self._load_plugin_module(self.plugins[plugin_id])
            with open(filepath, 'rb') as f:
                file_data = f.read()
            result = plugin_module.process(file_data)
            if not isinstance(result, bytes):
                raise ValueError('Plugin must return bytes')
            output_filename = os.path.join(app.config['PROCESSED_FOLDER'], os.path.basename(filepath) + '.processed')
            with open(output_filename, 'wb') as f:
                f.write(result)
            return output_filename
        except Exception as e:
            print(f'File processing failed: {e}')
            return None


processor = FileProcessor()


def _error_response(message, status_code):
    return jsonify({'error': message}), status_code


@app.route('/upload_plugin', methods=['POST'])
def upload_plugin():
    if 'plugin' not in request.files:
        return _error_response('No plugin file provided', 400)
    plugin_file = request.files['plugin']
    if plugin_file.filename == '':
        return _error_response('Empty filename', 400)
    if not plugin_file.filename.endswith('.py'):
        return _error_response('Only Python files (.py) are allowed', 400)
    plugin_id = processor.load_processing_plugin(plugin_file)
    if plugin_id:
        return jsonify({'plugin_id': plugin_id}), 200
    return _error_response('Plugin upload failed', 400)


@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return _error_response('No file provided', 400)
    if 'plugin_id' not in request.form:
        return _error_response('No plugin ID provided', 400)
    file = request.files['file']
    if file.filename == '':
        return _error_response('Empty filename', 400)
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    processed_file = processor.process_file(filepath, request.form['plugin_id'])
    if processed_file:
        processed_name = os.path.basename(processed_file)
        return jsonify({'processed_file': processed_name, 'download_url': f'/download/{processed_name}'}), 200
    return _error_response('File processing failed', 500)


@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    filepath = os.path.join(app.config['PROCESSED_FOLDER'], secure_filename(filename))
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return _error_response('File not found', 404)


@app.route('/status', methods=['GET'])
def status():
    return jsonify({'plugins_loaded': len(processor.plugins), 'jobs_processed': len(processor.jobs)}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
