import os
import csv
from flask import Flask, request, send_file, render_template, abort, jsonify

_BASE_DIR = os.path.dirname(__file__)

_REPORT_TEMPLATES_KEY = 'REPORT_TEMPLATES'
_DATA_SOURCES_KEY = 'DATA_SOURCES'
_OUTPUT_DIR_KEY = 'OUTPUT_DIR'

_TEMPLATES_DIR_NAME = 'templates'
_DATA_DIR_NAME = 'data'
_OUTPUT_DIR_NAME = 'reports'

_DEFAULT_TEMPLATE_NAME = 'default.tpl'
_SAMPLE_DATA_NAME = 'sample.csv'
_DEFAULT_OUTPUT_NAME = 'report.txt'
_INDEX_TEMPLATE_NAME = 'index.html'
_CSV_EXTENSION = '.csv'

_DEFAULT_TEMPLATE_CONTENT = 'Report Data:\n\n{data}'
_SAMPLE_DATA_CONTENT = 'id,name,value\n1,Test,100\n2,Example,200'

_ERROR_KEY = 'error'
_STATUS_KEY = 'status'
_STATUS_SUCCESS = 'success'
_REPORT_PATH_KEY = 'report_path'
_DOWNLOAD_URL_KEY = 'download_url'
_DOWNLOAD_URL_PREFIX = '/api/download/'

_MISSING_INPUT_MESSAGE = 'Missing template or data file'
_REPORT_NOT_FOUND_MESSAGE = 'Report not found'

_SERVER_HOST = '0.0.0.0'
_SERVER_PORT = 5000

app = Flask(__name__)
app.config[_REPORT_TEMPLATES_KEY] = os.path.join(_BASE_DIR, _TEMPLATES_DIR_NAME)
app.config[_DATA_SOURCES_KEY] = os.path.join(_BASE_DIR, _DATA_DIR_NAME)
app.config[_OUTPUT_DIR_KEY] = os.path.join(_BASE_DIR, _OUTPUT_DIR_NAME)


def _configured_path(config_key):
    return app.config[config_key]


def _configured_file_path(config_key, filename):
    return os.path.join(_configured_path(config_key), filename)


def _ensure_directory(path, exist_ok=False):
    if exist_ok:
        os.makedirs(path, exist_ok=True)
    elif not os.path.exists(path):
        os.makedirs(path)


def _read_text_file(path):
    with open(path, 'r') as f:
        return f.read()


def _write_text_file(path, content):
    with open(path, 'w') as f:
        f.write(content)


def _read_csv_rows(path):
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        return list(reader)


def _json_error(message, status_code):
    return (jsonify({_ERROR_KEY: message}), status_code)


class ReportGenerator:

    def __init__(self):
        _ensure_directory(_configured_path(_OUTPUT_DIR_KEY))

    def load_template(self, template_name):
        template_path = _configured_file_path(_REPORT_TEMPLATES_KEY, template_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f'Template {template_name} not found')
        return _read_text_file(template_path)

    def load_data(self, data_file):
        data_path = _configured_file_path(_DATA_SOURCES_KEY, data_file)
        if not os.path.exists(data_path):
            raise FileNotFoundError(f'Data file {data_file} not found')
        return _read_csv_rows(data_path)

    def generate_report(self, template_name, data_file, output_name):
        try:
            template = self.load_template(template_name)
            data = self.load_data(data_file)
            report_content = template.format(data=data)
            output_path = _configured_file_path(_OUTPUT_DIR_KEY, output_name)
            _write_text_file(output_path, report_content)
            return output_path
        except Exception as e:
            raise RuntimeError(f'Report generation failed: {str(e)}')


@app.route('/api/generate', methods=['POST'])
def generate_report():
    try:
        data = request.get_json()
        template = data.get('template')
        data_file = data.get('data_file')
        output_name = data.get('output_name', _DEFAULT_OUTPUT_NAME)
        if not template or not data_file:
            return _json_error(_MISSING_INPUT_MESSAGE, 400)
        generator = ReportGenerator()
        report_path = generator.generate_report(template, data_file, output_name)
        return jsonify({
            _STATUS_KEY: _STATUS_SUCCESS,
            _REPORT_PATH_KEY: report_path,
            _DOWNLOAD_URL_KEY: f'{_DOWNLOAD_URL_PREFIX}{os.path.basename(report_path)}'
        })
    except Exception as e:
        return _json_error(str(e), 500)


@app.route('/api/download/<filename>')
def download_report(filename):
    try:
        report_path = _configured_file_path(_OUTPUT_DIR_KEY, filename)
        if not os.path.exists(report_path):
            abort(404, _REPORT_NOT_FOUND_MESSAGE)
        return send_file(report_path, as_attachment=True)
    except Exception as e:
        abort(500, str(e))


@app.route('/')
def index():
    templates = []
    data_files = []
    try:
        templates = os.listdir(_configured_path(_REPORT_TEMPLATES_KEY))
        data_files = [f for f in os.listdir(_configured_path(_DATA_SOURCES_KEY)) if f.endswith(_CSV_EXTENSION)]
    except Exception:
        pass
    return render_template(_INDEX_TEMPLATE_NAME, templates=templates, data_files=data_files)


def _prepare_runtime_environment():
    _ensure_directory(_configured_path(_REPORT_TEMPLATES_KEY), exist_ok=True)
    _ensure_directory(_configured_path(_DATA_SOURCES_KEY), exist_ok=True)
    _ensure_directory(_configured_path(_OUTPUT_DIR_KEY), exist_ok=True)
    _write_text_file(
        _configured_file_path(_REPORT_TEMPLATES_KEY, _DEFAULT_TEMPLATE_NAME),
        _DEFAULT_TEMPLATE_CONTENT
    )
    _write_text_file(
        _configured_file_path(_DATA_SOURCES_KEY, _SAMPLE_DATA_NAME),
        _SAMPLE_DATA_CONTENT
    )


if __name__ == '__main__':
    _prepare_runtime_environment()
    app.run(host=_SERVER_HOST, port=_SERVER_PORT)
