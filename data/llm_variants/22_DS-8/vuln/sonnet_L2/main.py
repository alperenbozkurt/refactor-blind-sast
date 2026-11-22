import os
import csv
import json
from flask import Flask, request, send_file, abort
from jinja2 import Template

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

CONFIG_TEMPLATE_DIR = 'TEMPLATE_DIR'
CONFIG_REPORT_OUTPUT_DIR = 'REPORT_OUTPUT_DIR'
CONFIG_DATA_SOURCES_DIR = 'DATA_SOURCES_DIR'

DEFAULT_TEMPLATE_DIR = './templates'
DEFAULT_REPORT_OUTPUT_DIR = './reports'
DEFAULT_DATA_SOURCES_DIR = './data_sources'

DEFAULT_OUTPUT_FORMAT = 'html'
JSON_EXTENSION = '.json'
CSV_EXTENSION = '.csv'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500

app = Flask(__name__)
app.config[CONFIG_TEMPLATE_DIR] = DEFAULT_TEMPLATE_DIR
app.config[CONFIG_REPORT_OUTPUT_DIR] = DEFAULT_REPORT_OUTPUT_DIR
app.config[CONFIG_DATA_SOURCES_DIR] = DEFAULT_DATA_SOURCES_DIR


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _config_dir(key):
    """Return the configured directory (read at call time, so changes apply)."""
    return app.config[key]


def _list_files(directory):
    """Return names of regular files directly inside ``directory``."""
    return [
        name for name in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, name))
    ]


def _read_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def _read_csv(path):
    with open(path, 'r') as f:
        return list(csv.DictReader(f))


def _build_output_filename(template_file, output_format):
    return f'report_{os.path.splitext(template_file)[0]}.{output_format}'


# --------------------------------------------------------------------------- #
# Core logic
# --------------------------------------------------------------------------- #

class ReportGenerator:

    def __init__(self):
        for key in (CONFIG_TEMPLATE_DIR, CONFIG_REPORT_OUTPUT_DIR, CONFIG_DATA_SOURCES_DIR):
            os.makedirs(_config_dir(key), exist_ok=True)

    def load_template(self, template_name):
        template_path = os.path.join(_config_dir(CONFIG_TEMPLATE_DIR), template_name)
        try:
            with open(template_path, 'r') as f:
                return Template(f.read())
        except Exception:
            return None

    def load_data_source(self, data_file):
        data_path = os.path.join(_config_dir(CONFIG_DATA_SOURCES_DIR), data_file)
        try:
            if data_file.endswith(JSON_EXTENSION):
                return _read_json(data_path)
            elif data_file.endswith(CSV_EXTENSION):
                return _read_csv(data_path)
            else:
                return None
        except Exception:
            return None

    def generate_report(self, template_file, data_file, output_format=DEFAULT_OUTPUT_FORMAT):
        template = self.load_template(template_file)
        data = self.load_data_source(data_file)
        if not template or not data:
            return None
        report_content = template.render(data=data)
        output_filename = _build_output_filename(template_file, output_format)
        output_path = os.path.join(_config_dir(CONFIG_REPORT_OUTPUT_DIR), output_filename)
        try:
            with open(output_path, 'w') as f:
                f.write(report_content)
            return output_path
        except Exception:
            return None


report_generator = ReportGenerator()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.route('/report', methods=['POST'])
def create_report():
    data = request.get_json()
    if not data or 'template' not in data or 'data_source' not in data:
        abort(HTTP_BAD_REQUEST, description='Missing template or data_source')
    output_format = data.get('format', DEFAULT_OUTPUT_FORMAT)
    report_path = report_generator.generate_report(
        data['template'], data['data_source'], output_format
    )
    if report_path:
        return ({'status': 'success', 'report_path': os.path.basename(report_path)}, HTTP_CREATED)
    else:
        return ({'error': 'Failed to generate report'}, HTTP_SERVER_ERROR)


@app.route('/report/download/<path:report_file>')
def download_report(report_file):
    report_path = os.path.join(_config_dir(CONFIG_REPORT_OUTPUT_DIR), report_file)
    if not os.path.exists(report_path):
        abort(HTTP_NOT_FOUND, description='Report not found')
    try:
        return send_file(report_path, as_attachment=True)
    except Exception as e:
        abort(HTTP_SERVER_ERROR, description=str(e))


@app.route('/templates')
def list_templates():
    try:
        templates = _list_files(_config_dir(CONFIG_TEMPLATE_DIR))
        return {'templates': templates}
    except Exception as e:
        abort(HTTP_SERVER_ERROR, description=str(e))


@app.route('/data_sources')
def list_data_sources():
    try:
        data_files = _list_files(_config_dir(CONFIG_DATA_SOURCES_DIR))
        return {'data_sources': data_files}
    except Exception as e:
        abort(HTTP_SERVER_ERROR, description=str(e))


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT)
