import os
import csv
from flask import Flask, request, send_file, render_template, abort, jsonify

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
BASE_DIR = os.path.dirname(__file__)

CONFIG_REPORT_TEMPLATES = 'REPORT_TEMPLATES'
CONFIG_DATA_SOURCES = 'DATA_SOURCES'
CONFIG_OUTPUT_DIR = 'OUTPUT_DIR'

TEMPLATES_DIRNAME = 'templates'
DATA_DIRNAME = 'data'
OUTPUT_DIRNAME = 'reports'

DEFAULT_OUTPUT_NAME = 'report.txt'
DATA_FILE_EXTENSION = '.csv'
INDEX_TEMPLATE = 'index.html'
DOWNLOAD_URL_PREFIX = '/api/download/'

DEFAULT_TEMPLATE_NAME = 'default.tpl'
DEFAULT_TEMPLATE_CONTENT = 'Report Data:\n\n{data}'
SAMPLE_DATA_NAME = 'sample.csv'
SAMPLE_DATA_CONTENT = 'id,name,value\n1,Test,100\n2,Example,200'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #
app = Flask(__name__)
app.config[CONFIG_REPORT_TEMPLATES] = os.path.join(BASE_DIR, TEMPLATES_DIRNAME)
app.config[CONFIG_DATA_SOURCES] = os.path.join(BASE_DIR, DATA_DIRNAME)
app.config[CONFIG_OUTPUT_DIR] = os.path.join(BASE_DIR, OUTPUT_DIRNAME)


# --------------------------------------------------------------------------- #
# Path helpers (config is read at call time so runtime changes are honoured)
# --------------------------------------------------------------------------- #
def _templates_dir():
    return app.config[CONFIG_REPORT_TEMPLATES]


def _data_dir():
    return app.config[CONFIG_DATA_SOURCES]


def _output_dir():
    return app.config[CONFIG_OUTPUT_DIR]


def _template_path(template_name):
    return os.path.join(_templates_dir(), template_name)


def _data_path(data_file):
    return os.path.join(_data_dir(), data_file)


def _output_path(output_name):
    return os.path.join(_output_dir(), output_name)


def _read_text(path):
    with open(path, 'r') as f:
        return f.read()


def _write_text(path, content):
    with open(path, 'w') as f:
        f.write(content)


def _read_csv_rows(path):
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        return list(reader)


# --------------------------------------------------------------------------- #
# Domain logic
# --------------------------------------------------------------------------- #
class ReportGenerator:

    def __init__(self):
        if not os.path.exists(_output_dir()):
            os.makedirs(_output_dir())

    def load_template(self, template_name):
        template_path = _template_path(template_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f'Template {template_name} not found')
        return _read_text(template_path)

    def load_data(self, data_file):
        data_path = _data_path(data_file)
        if not os.path.exists(data_path):
            raise FileNotFoundError(f'Data file {data_file} not found')
        return _read_csv_rows(data_path)

    def generate_report(self, template_name, data_file, output_name):
        try:
            template = self.load_template(template_name)
            data = self.load_data(data_file)
            report_content = template.format(data=data)
            output_path = _output_path(output_name)
            _write_text(output_path, report_content)
            return output_path
        except Exception as e:
            raise RuntimeError(f'Report generation failed: {str(e)}')


# --------------------------------------------------------------------------- #
# Listing helpers for the index page
# --------------------------------------------------------------------------- #
def _list_data_files():
    return [f for f in os.listdir(_data_dir()) if f.endswith(DATA_FILE_EXTENSION)]


def _error_response(message, status):
    return (jsonify({'error': message}), status)


def _download_url(report_path):
    return f'{DOWNLOAD_URL_PREFIX}{os.path.basename(report_path)}'


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/api/generate', methods=['POST'])
def generate_report():
    try:
        data = request.get_json()
        template = data.get('template')
        data_file = data.get('data_file')
        output_name = data.get('output_name', DEFAULT_OUTPUT_NAME)
        if not template or not data_file:
            return _error_response('Missing template or data file', 400)
        generator = ReportGenerator()
        report_path = generator.generate_report(template, data_file, output_name)
        return jsonify({
            'status': 'success',
            'report_path': report_path,
            'download_url': _download_url(report_path),
        })
    except Exception as e:
        return _error_response(str(e), 500)


@app.route('/api/download/<filename>')
def download_report(filename):
    try:
        report_path = _output_path(filename)
        if not os.path.exists(report_path):
            abort(404, 'Report not found')
        return send_file(report_path, as_attachment=True)
    except Exception as e:
        abort(500, str(e))


@app.route('/')
def index():
    templates = []
    data_files = []
    try:
        templates = os.listdir(_templates_dir())
        data_files = _list_data_files()
    except Exception:
        pass
    return render_template(INDEX_TEMPLATE, templates=templates, data_files=data_files)


# --------------------------------------------------------------------------- #
# Command-line entry point
# --------------------------------------------------------------------------- #
def _bootstrap_workspace():
    os.makedirs(_templates_dir(), exist_ok=True)
    os.makedirs(_data_dir(), exist_ok=True)
    os.makedirs(_output_dir(), exist_ok=True)
    _write_text(os.path.join(_templates_dir(), DEFAULT_TEMPLATE_NAME), DEFAULT_TEMPLATE_CONTENT)
    _write_text(os.path.join(_data_dir(), SAMPLE_DATA_NAME), SAMPLE_DATA_CONTENT)


if __name__ == '__main__':
    _bootstrap_workspace()
    app.run(host=SERVER_HOST, port=SERVER_PORT)
