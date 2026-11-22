import os
import csv
from flask import Flask, request, send_file, render_template, abort, jsonify
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
BASE_DIR = os.path.dirname(__file__)

TEMPLATE_EXTENSION = '.tpl'
CSV_EXTENSION = '.csv'
TEXT_EXTENSION = '.txt'

DEFAULT_OUTPUT_NAME = 'report.txt'
DOWNLOAD_URL_PREFIX = '/api/download/'

DIR_MODE = 0o750   # 488
FILE_MODE = 0o640  # 416

SAMPLE_TEMPLATE_NAME = 'default.tpl'
SAMPLE_TEMPLATE_CONTENT = 'Report Data:\n\n{data}'
SAMPLE_DATA_NAME = 'sample.csv'
SAMPLE_DATA_CONTENT = 'id,name,value\n1,Test,100\n2,Example,200'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

# --------------------------------------------------------------------------- #
# Application and configuration
# --------------------------------------------------------------------------- #
app = Flask(__name__)
app.config['REPORT_TEMPLATES'] = os.path.abspath(os.path.join(BASE_DIR, 'templates'))
app.config['DATA_SOURCES'] = os.path.abspath(os.path.join(BASE_DIR, 'data'))
app.config['OUTPUT_DIR'] = os.path.abspath(os.path.join(BASE_DIR, 'reports'))
app.config['ALLOWED_EXTENSIONS'] = {TEMPLATE_EXTENSION, CSV_EXTENSION, TEXT_EXTENSION}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _list_files(directory, extension):
    """Return names of regular files in ``directory`` ending with ``extension``."""
    return [
        name
        for name in os.listdir(directory)
        if name.endswith(extension) and os.path.isfile(os.path.join(directory, name))
    ]


def _write_sample_file(path, content, description):
    """Write a sample file with restricted permissions, logging any failure."""
    try:
        with open(path, 'w') as f:
            f.write(content)
        os.chmod(path, FILE_MODE)
    except Exception as e:
        app.logger.error(f'Error creating sample {description}: {e}')


def _ensure_directories():
    for key in ('REPORT_TEMPLATES', 'DATA_SOURCES', 'OUTPUT_DIR'):
        os.makedirs(app.config[key], mode=DIR_MODE, exist_ok=True)


def _create_sample_files():
    template_path = os.path.join(app.config['REPORT_TEMPLATES'], SAMPLE_TEMPLATE_NAME)
    _write_sample_file(template_path, SAMPLE_TEMPLATE_CONTENT, 'template')
    data_path = os.path.join(app.config['DATA_SOURCES'], SAMPLE_DATA_NAME)
    _write_sample_file(data_path, SAMPLE_DATA_CONTENT, 'data')


# --------------------------------------------------------------------------- #
# Report generation
# --------------------------------------------------------------------------- #
class ReportGenerator:

    def __init__(self):
        os.makedirs(app.config['OUTPUT_DIR'], exist_ok=True)

    def is_safe_path(self, base_path, requested_path):
        base_path = os.path.abspath(base_path)
        requested_path = os.path.abspath(requested_path)
        return requested_path.startswith(base_path + os.sep)

    def is_allowed_file(self, filename, allowed_extensions):
        if not filename or not isinstance(filename, str):
            return False
        if not any((filename.endswith(ext) for ext in allowed_extensions)):
            return False
        if '../' in filename or '~' in filename:
            return False
        return True

    def _resolve_existing_file(self, base_dir, filename, extension,
                               invalid_name_msg, invalid_path_msg, not_found_msg):
        """Validate ``filename`` and return its path inside ``base_dir``."""
        if not self.is_allowed_file(filename, {extension}):
            raise ValueError(invalid_name_msg)
        path = os.path.join(base_dir, filename)
        if not self.is_safe_path(base_dir, path):
            raise ValueError(invalid_path_msg)
        if not os.path.exists(path):
            raise FileNotFoundError(not_found_msg)
        return path

    def load_template(self, template_name):
        template_path = self._resolve_existing_file(
            app.config['REPORT_TEMPLATES'], template_name, TEMPLATE_EXTENSION,
            'Invalid template name', 'Invalid template path', 'Template not found')
        with open(template_path, 'r') as f:
            return f.read()

    def load_data(self, data_file):
        data_path = self._resolve_existing_file(
            app.config['DATA_SOURCES'], data_file, CSV_EXTENSION,
            'Invalid data file name', 'Invalid data path', 'Data file not found')
        with open(data_path, 'r') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _build_output_path(self, output_name):
        output_path = os.path.join(app.config['OUTPUT_DIR'], secure_filename(output_name))
        if not self.is_safe_path(app.config['OUTPUT_DIR'], output_path):
            raise ValueError('Invalid output path')
        return output_path

    def generate_report(self, template_name, data_file, output_name):
        try:
            if not self.is_allowed_file(output_name, {TEXT_EXTENSION}):
                raise ValueError('Invalid output file name')
            template = self.load_template(template_name)
            data = self.load_data(data_file)
            report_content = template.format(data=data)
            output_path = self._build_output_path(output_name)
            with open(output_path, 'w') as f:
                f.write(report_content)
            return output_path
        except Exception as e:
            raise RuntimeError(f'Report generation failed: {str(e)}')


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
def _error_response(message, status):
    return (jsonify({'error': message}), status)


@app.route('/api/generate', methods=['POST'])
def generate_report():
    try:
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return _error_response('Invalid request', 400)
        template = data.get('template')
        data_file = data.get('data_file')
        output_name = secure_filename(data.get('output_name', DEFAULT_OUTPUT_NAME))
        if not template or not data_file:
            return _error_response('Missing template or data file', 400)
        generator = ReportGenerator()
        report_path = generator.generate_report(template, data_file, output_name)
        report_name = os.path.basename(report_path)
        return jsonify({
            'status': 'success',
            'report_path': report_name,
            'download_url': f'{DOWNLOAD_URL_PREFIX}{report_name}',
        })
    except ValueError as e:
        return _error_response(str(e), 400)
    except FileNotFoundError as e:
        return _error_response(str(e), 404)
    except Exception as e:
        app.logger.error(f'Report generation error: {e}')
        return _error_response('Internal server error', 500)


@app.route('/api/download/<filename>')
def download_report(filename):
    try:
        if not filename or not isinstance(filename, str):
            abort(400, 'Invalid filename')
        safe_filename = secure_filename(filename)
        report_path = os.path.join(app.config['OUTPUT_DIR'], safe_filename)
        if not os.path.exists(report_path):
            abort(404, 'Report not found')
        return send_file(report_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Download error: {e}')
        abort(500, 'Internal server error')


@app.route('/')
def index():
    templates = []
    data_files = []
    try:
        templates = _list_files(app.config['REPORT_TEMPLATES'], TEMPLATE_EXTENSION)
        data_files = _list_files(app.config['DATA_SOURCES'], CSV_EXTENSION)
    except Exception as e:
        app.logger.error(f'Directory listing error: {e}')
    return render_template('index.html', templates=templates, data_files=data_files)


# --------------------------------------------------------------------------- #
# Command-line entry point
# --------------------------------------------------------------------------- #
if __name__ == '__main__':
    _ensure_directories()
    _create_sample_files()
    app.run(host=SERVER_HOST, port=SERVER_PORT)
