"""Flask service for rendering reports from Jinja2 templates and data sources."""

import csv
import json
import os

from flask import Flask, abort, request, send_file
from jinja2 import Template

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG_TEMPLATE_DIR = 'TEMPLATE_DIR'
CONFIG_REPORT_OUTPUT_DIR = 'REPORT_OUTPUT_DIR'
CONFIG_DATA_SOURCES_DIR = 'DATA_SOURCES_DIR'

DEFAULT_CONFIG = {
    CONFIG_TEMPLATE_DIR: './templates',
    CONFIG_REPORT_OUTPUT_DIR: './reports',
    CONFIG_DATA_SOURCES_DIR: './data_sources',
}

# Directories created on ReportGenerator initialisation (order preserved).
MANAGED_DIRECTORY_KEYS = (
    CONFIG_TEMPLATE_DIR,
    CONFIG_REPORT_OUTPUT_DIR,
    CONFIG_DATA_SOURCES_DIR,
)

JSON_EXTENSION = '.json'
CSV_EXTENSION = '.csv'
DEFAULT_OUTPUT_FORMAT = 'html'
REPORT_FILENAME_PREFIX = 'report_'

# Request / response field names.
PARAM_TEMPLATE = 'template'
PARAM_DATA_SOURCE = 'data_source'
PARAM_FORMAT = 'format'

KEY_STATUS = 'status'
KEY_REPORT_PATH = 'report_path'
KEY_ERROR = 'error'
KEY_TEMPLATES = 'templates'
KEY_DATA_SOURCES = 'data_sources'

STATUS_SUCCESS = 'success'

ERROR_MISSING_PARAMETERS = 'Missing template or data_source'
ERROR_REPORT_NOT_FOUND = 'Report not found'
ERROR_GENERATION_FAILED = 'Failed to generate report'

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_CREATED = 201

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

app = Flask(__name__)
app.config.update(DEFAULT_CONFIG)


# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------

def read_text_file(path):
    with open(path, 'r') as file:
        return file.read()


def write_text_file(path, content):
    with open(path, 'w') as file:
        file.write(content)


def load_json_file(path):
    with open(path, 'r') as file:
        return json.load(file)


def load_csv_file(path):
    with open(path, 'r') as file:
        return list(csv.DictReader(file))


# Data-source loaders keyed by the file extension they handle.
DATA_LOADERS = {
    JSON_EXTENSION: load_json_file,
    CSV_EXTENSION: load_csv_file,
}


def list_regular_files(directory):
    return [
        name
        for name in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, name))
    ]


def build_report_filename(template_file, output_format):
    template_stem = os.path.splitext(template_file)[0]
    return f'{REPORT_FILENAME_PREFIX}{template_stem}.{output_format}'


def directory_listing_response(config_key, response_key):
    try:
        return {response_key: list_regular_files(app.config[config_key])}
    except Exception as e:
        abort(HTTP_INTERNAL_SERVER_ERROR, description=str(e))


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

class ReportGenerator:

    def __init__(self):
        for config_key in MANAGED_DIRECTORY_KEYS:
            os.makedirs(app.config[config_key], exist_ok=True)

    def load_template(self, template_name):
        template_path = os.path.join(app.config[CONFIG_TEMPLATE_DIR], template_name)
        try:
            return Template(read_text_file(template_path))
        except Exception:
            return None

    def load_data_source(self, data_file):
        data_path = os.path.join(app.config[CONFIG_DATA_SOURCES_DIR], data_file)
        try:
            for extension, loader in DATA_LOADERS.items():
                if data_file.endswith(extension):
                    return loader(data_path)
            return None
        except Exception:
            return None

    def generate_report(self, template_file, data_file, output_format=DEFAULT_OUTPUT_FORMAT):
        template = self.load_template(template_file)
        data = self.load_data_source(data_file)
        if not template or not data:
            return None
        report_content = template.render(data=data)
        output_filename = build_report_filename(template_file, output_format)
        output_path = os.path.join(app.config[CONFIG_REPORT_OUTPUT_DIR], output_filename)
        try:
            write_text_file(output_path, report_content)
            return output_path
        except Exception:
            return None


report_generator = ReportGenerator()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/report', methods=['POST'])
def create_report():
    data = request.get_json()
    if not data or PARAM_TEMPLATE not in data or PARAM_DATA_SOURCE not in data:
        abort(HTTP_BAD_REQUEST, description=ERROR_MISSING_PARAMETERS)
    output_format = data.get(PARAM_FORMAT, DEFAULT_OUTPUT_FORMAT)
    report_path = report_generator.generate_report(
        data[PARAM_TEMPLATE], data[PARAM_DATA_SOURCE], output_format
    )
    if report_path:
        return (
            {KEY_STATUS: STATUS_SUCCESS, KEY_REPORT_PATH: os.path.basename(report_path)},
            HTTP_CREATED,
        )
    else:
        return ({KEY_ERROR: ERROR_GENERATION_FAILED}, HTTP_INTERNAL_SERVER_ERROR)


@app.route('/report/download/<path:report_file>')
def download_report(report_file):
    report_path = os.path.join(app.config[CONFIG_REPORT_OUTPUT_DIR], report_file)
    if not os.path.exists(report_path):
        abort(HTTP_NOT_FOUND, description=ERROR_REPORT_NOT_FOUND)
    try:
        return send_file(report_path, as_attachment=True)
    except Exception as e:
        abort(HTTP_INTERNAL_SERVER_ERROR, description=str(e))


@app.route('/templates')
def list_templates():
    return directory_listing_response(CONFIG_TEMPLATE_DIR, KEY_TEMPLATES)


@app.route('/data_sources')
def list_data_sources():
    return directory_listing_response(CONFIG_DATA_SOURCES_DIR, KEY_DATA_SOURCES)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT)
