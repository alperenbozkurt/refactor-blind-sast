"""Flask report-generation service.

Renders Jinja2 templates against JSON/CSV data sources, writes the
rendered reports to disk and exposes them for download over HTTP.
"""

import csv
import json
import os

from flask import Flask, abort, request, send_file
from jinja2 import Template, escape
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 5000

DEFAULT_OUTPUT_FORMAT = 'html'
SUPPORTED_OUTPUT_FORMATS = frozenset({'html', 'txt'})
DOWNLOADABLE_EXTENSIONS = frozenset({'.html', '.txt'})

JSON_EXTENSION = '.json'
CSV_EXTENSION = '.csv'

PATH_TRAVERSAL_TOKENS = ('../', '~')

MANAGED_DIRECTORY_CONFIG_KEYS = (
    'TEMPLATE_DIR',
    'REPORT_OUTPUT_DIR',
    'DATA_SOURCES_DIR',
)

ERROR_INVALID_REQUEST = 'Invalid request'
ERROR_INVALID_INPUT_TYPE = 'Invalid input type'
ERROR_INVALID_FILE_TYPE = 'Invalid file type'
ERROR_ACCESS_DENIED = 'Access denied'
ERROR_REPORT_NOT_FOUND = 'Report not found'
ERROR_INTERNAL_SERVER = 'Internal server error'


# ---------------------------------------------------------------------------
# Application configuration
# ---------------------------------------------------------------------------

class AppConfig:
    """Default filesystem layout and file-restriction settings."""

    TEMPLATE_DIR = os.path.abspath('./templates')
    REPORT_OUTPUT_DIR = os.path.abspath('./reports')
    DATA_SOURCES_DIR = os.path.abspath('./data_sources')
    ALLOWED_TEMPLATE_EXT = '.html'
    ALLOWED_DATA_EXTENSIONS = {'.json', '.csv'}


app = Flask(__name__)
app.config.from_object(AppConfig)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _ensure_directory(path):
    """Create ``path`` (and any parents) if it does not already exist."""
    os.makedirs(path, exist_ok=True)


def _escape_mapping(mapping):
    """Return a copy of ``mapping`` with every value HTML-escaped."""
    return {key: escape(str(value)) for key, value in mapping.items()}


def _list_allowed_files(directory, allowed_extensions):
    """List regular files in ``directory`` whose names pass the filter."""
    return [
        filename
        for filename in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, filename))
        and report_generator.is_allowed_file(filename, allowed_extensions)
    ]


def _validated_report_payload():
    """Return the JSON body of the report request, aborting on bad input."""
    data = request.get_json()
    if not data or 'template' not in data or 'data_source' not in data:
        abort(400, description=ERROR_INVALID_REQUEST)
    if not isinstance(data['template'], str) or not isinstance(data['data_source'], str):
        abort(400, description=ERROR_INVALID_INPUT_TYPE)
    return data


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Loads templates and data sources and renders report files."""

    def __init__(self):
        for config_key in MANAGED_DIRECTORY_CONFIG_KEYS:
            _ensure_directory(app.config[config_key])

    def is_safe_path(self, base, path):
        base = os.path.abspath(base)
        path = os.path.abspath(path)
        return path.startswith(base + os.sep)

    def is_allowed_file(self, filename, allowed_extensions):
        if not filename:
            return False
        if not any(filename.endswith(ext) for ext in allowed_extensions):
            return False
        if any(token in filename for token in PATH_TRAVERSAL_TOKENS):
            return False
        return True

    def load_template(self, template_name):
        if not self.is_allowed_file(template_name, {app.config['ALLOWED_TEMPLATE_EXT']}):
            return None
        template_path = os.path.join(app.config['TEMPLATE_DIR'], template_name)
        if not self.is_safe_path(app.config['TEMPLATE_DIR'], template_path):
            return None
        try:
            with open(template_path, 'r') as file_obj:
                return Template(escape(file_obj.read()))
        except Exception as exc:
            app.logger.error(f'Template load error: {exc}')
            return None

    def load_data_source(self, data_file):
        if not self.is_allowed_file(data_file, app.config['ALLOWED_DATA_EXTENSIONS']):
            return None
        data_path = os.path.join(app.config['DATA_SOURCES_DIR'], data_file)
        if not self.is_safe_path(app.config['DATA_SOURCES_DIR'], data_path):
            return None
        try:
            if data_file.endswith(JSON_EXTENSION):
                return self._load_json_data(data_path)
            if data_file.endswith(CSV_EXTENSION):
                return self._load_csv_data(data_path)
            return None
        except Exception as exc:
            app.logger.error(f'Data load error: {exc}')
            return None

    def generate_report(self, template_file, data_file, output_format='html'):
        if output_format not in SUPPORTED_OUTPUT_FORMATS:
            return None
        template = self.load_template(template_file)
        data = self.load_data_source(data_file)
        if not template or not data:
            return None
        try:
            report_content = template.render(data=data)
            output_path = self._build_output_path(template_file, output_format)
            if not self.is_safe_path(app.config['REPORT_OUTPUT_DIR'], output_path):
                return None
            with open(output_path, 'w') as file_obj:
                file_obj.write(report_content)
            return output_path
        except Exception as exc:
            app.logger.error(f'Report generation error: {exc}')
            return None

    @staticmethod
    def _load_json_data(data_path):
        with open(data_path, 'r') as file_obj:
            data = json.load(file_obj)
        if isinstance(data, dict):
            return _escape_mapping(data)
        if isinstance(data, list):
            return [_escape_mapping(item) for item in data]
        return data

    @staticmethod
    def _load_csv_data(data_path):
        with open(data_path, 'r') as file_obj:
            return [_escape_mapping(row) for row in csv.DictReader(file_obj)]

    @staticmethod
    def _build_output_path(template_file, output_format):
        safe_filename = secure_filename(
            f'report_{os.path.splitext(template_file)[0]}.{output_format}'
        )
        return os.path.join(app.config['REPORT_OUTPUT_DIR'], safe_filename)


report_generator = ReportGenerator()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/report', methods=['POST'])
def create_report():
    data = _validated_report_payload()
    output_format = data.get('format', DEFAULT_OUTPUT_FORMAT)
    report_path = report_generator.generate_report(
        data['template'], data['data_source'], output_format
    )
    if report_path:
        return ({'status': 'success', 'report_path': os.path.basename(report_path)}, 201)
    return ({'error': 'Report generation failed'}, 500)


@app.route('/report/download/<path:report_file>')
def download_report(report_file):
    if not report_generator.is_allowed_file(report_file, DOWNLOADABLE_EXTENSIONS):
        abort(400, description=ERROR_INVALID_FILE_TYPE)
    report_path = os.path.join(app.config['REPORT_OUTPUT_DIR'], report_file)
    if not report_generator.is_safe_path(app.config['REPORT_OUTPUT_DIR'], report_path):
        abort(403, description=ERROR_ACCESS_DENIED)
    if not os.path.exists(report_path):
        abort(404, description=ERROR_REPORT_NOT_FOUND)
    try:
        return send_file(report_path, as_attachment=True)
    except Exception as exc:
        app.logger.error(f'Download error: {exc}')
        abort(500, description=ERROR_INTERNAL_SERVER)


@app.route('/templates')
def list_templates():
    try:
        templates = _list_allowed_files(
            app.config['TEMPLATE_DIR'], {app.config['ALLOWED_TEMPLATE_EXT']}
        )
        return {'templates': templates}
    except Exception as exc:
        app.logger.error(f'Template list error: {exc}')
        abort(500, description=ERROR_INTERNAL_SERVER)


@app.route('/data_sources')
def list_data_sources():
    try:
        data_files = _list_allowed_files(
            app.config['DATA_SOURCES_DIR'], app.config['ALLOWED_DATA_EXTENSIONS']
        )
        return {'data_sources': data_files}
    except Exception as exc:
        app.logger.error(f'Data source list error: {exc}')
        abort(500, description=ERROR_INTERNAL_SERVER)


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(host=DEFAULT_HOST, port=DEFAULT_PORT)
