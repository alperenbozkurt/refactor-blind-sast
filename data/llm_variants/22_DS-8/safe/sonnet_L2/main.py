import os
import csv
import json
from flask import Flask, request, send_file, abort
from jinja2 import Template, escape
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
DEFAULT_TEMPLATE_DIR = './templates'
DEFAULT_REPORT_OUTPUT_DIR = './reports'
DEFAULT_DATA_SOURCES_DIR = './data_sources'
DEFAULT_ALLOWED_TEMPLATE_EXT = '.html'
DEFAULT_ALLOWED_DATA_EXTENSIONS = {'.json', '.csv'}

JSON_EXT = '.json'
CSV_EXT = '.csv'

DEFAULT_OUTPUT_FORMAT = 'html'
ALLOWED_OUTPUT_FORMATS = {'html', 'txt'}
ALLOWED_REPORT_DOWNLOAD_EXTENSIONS = {'.html', '.txt'}

FORBIDDEN_FILENAME_FRAGMENTS = ('../', '~')

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000


# --------------------------------------------------------------------------
# Application setup
# --------------------------------------------------------------------------
def configure_app(flask_app):
    """Populate the Flask application configuration with default values."""
    flask_app.config['TEMPLATE_DIR'] = os.path.abspath(DEFAULT_TEMPLATE_DIR)
    flask_app.config['REPORT_OUTPUT_DIR'] = os.path.abspath(DEFAULT_REPORT_OUTPUT_DIR)
    flask_app.config['DATA_SOURCES_DIR'] = os.path.abspath(DEFAULT_DATA_SOURCES_DIR)
    flask_app.config['ALLOWED_TEMPLATE_EXT'] = DEFAULT_ALLOWED_TEMPLATE_EXT
    flask_app.config['ALLOWED_DATA_EXTENSIONS'] = set(DEFAULT_ALLOWED_DATA_EXTENSIONS)
    return flask_app


app = configure_app(Flask(__name__))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _escape_mapping(mapping):
    """Return a copy of ``mapping`` with all values stringified and escaped."""
    return {k: escape(str(v)) for (k, v) in mapping.items()}


def _read_json_data(path):
    with open(path, 'r') as f:
        data = json.load(f)
        if isinstance(data, dict):
            return _escape_mapping(data)
        elif isinstance(data, list):
            return [_escape_mapping(item) for item in data]
        return data


def _read_csv_data(path):
    with open(path, 'r') as f:
        return [_escape_mapping(row) for row in csv.DictReader(f)]


def _list_allowed_files(directory, allowed_extensions, checker):
    return [
        f for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
        and checker(f, allowed_extensions)
    ]


# --------------------------------------------------------------------------
# Report generation
# --------------------------------------------------------------------------
class ReportGenerator:

    def __init__(self):
        for key in ('TEMPLATE_DIR', 'REPORT_OUTPUT_DIR', 'DATA_SOURCES_DIR'):
            os.makedirs(app.config[key], exist_ok=True)

    def is_safe_path(self, base, path):
        base = os.path.abspath(base)
        path = os.path.abspath(path)
        return path.startswith(base + os.sep)

    def is_allowed_file(self, filename, allowed_extensions):
        if not filename:
            return False
        if not any((filename.endswith(ext) for ext in allowed_extensions)):
            return False
        if any(fragment in filename for fragment in FORBIDDEN_FILENAME_FRAGMENTS):
            return False
        return True

    def load_template(self, template_name):
        if not self.is_allowed_file(template_name, {app.config['ALLOWED_TEMPLATE_EXT']}):
            return None
        template_path = os.path.join(app.config['TEMPLATE_DIR'], template_name)
        if not self.is_safe_path(app.config['TEMPLATE_DIR'], template_path):
            return None
        try:
            with open(template_path, 'r') as f:
                return Template(escape(f.read()))
        except Exception as e:
            app.logger.error(f'Template load error: {e}')
            return None

    def load_data_source(self, data_file):
        if not self.is_allowed_file(data_file, app.config['ALLOWED_DATA_EXTENSIONS']):
            return None
        data_path = os.path.join(app.config['DATA_SOURCES_DIR'], data_file)
        if not self.is_safe_path(app.config['DATA_SOURCES_DIR'], data_path):
            return None
        try:
            if data_file.endswith(JSON_EXT):
                return _read_json_data(data_path)
            elif data_file.endswith(CSV_EXT):
                return _read_csv_data(data_path)
            else:
                return None
        except Exception as e:
            app.logger.error(f'Data load error: {e}')
            return None

    def generate_report(self, template_file, data_file, output_format=DEFAULT_OUTPUT_FORMAT):
        if output_format not in ALLOWED_OUTPUT_FORMATS:
            return None
        template = self.load_template(template_file)
        data = self.load_data_source(data_file)
        if not template or not data:
            return None
        try:
            report_content = template.render(data=data)
            safe_filename = secure_filename(
                f'report_{os.path.splitext(template_file)[0]}.{output_format}'
            )
            output_path = os.path.join(app.config['REPORT_OUTPUT_DIR'], safe_filename)
            if not self.is_safe_path(app.config['REPORT_OUTPUT_DIR'], output_path):
                return None
            with open(output_path, 'w') as f:
                f.write(report_content)
            return output_path
        except Exception as e:
            app.logger.error(f'Report generation error: {e}')
            return None


report_generator = ReportGenerator()


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route('/report', methods=['POST'])
def create_report():
    data = request.get_json()
    if not data or 'template' not in data or 'data_source' not in data:
        abort(400, description='Invalid request')
    if not isinstance(data['template'], str) or not isinstance(data['data_source'], str):
        abort(400, description='Invalid input type')
    output_format = data.get('format', DEFAULT_OUTPUT_FORMAT)
    report_path = report_generator.generate_report(
        data['template'], data['data_source'], output_format
    )
    if report_path:
        return ({'status': 'success', 'report_path': os.path.basename(report_path)}, 201)
    else:
        return ({'error': 'Report generation failed'}, 500)


@app.route('/report/download/<path:report_file>')
def download_report(report_file):
    if not report_generator.is_allowed_file(report_file, ALLOWED_REPORT_DOWNLOAD_EXTENSIONS):
        abort(400, description='Invalid file type')
    report_path = os.path.join(app.config['REPORT_OUTPUT_DIR'], report_file)
    if not report_generator.is_safe_path(app.config['REPORT_OUTPUT_DIR'], report_path):
        abort(403, description='Access denied')
    if not os.path.exists(report_path):
        abort(404, description='Report not found')
    try:
        return send_file(report_path, as_attachment=True)
    except Exception as e:
        app.logger.error(f'Download error: {e}')
        abort(500, description='Internal server error')


@app.route('/templates')
def list_templates():
    try:
        templates = _list_allowed_files(
            app.config['TEMPLATE_DIR'],
            {app.config['ALLOWED_TEMPLATE_EXT']},
            report_generator.is_allowed_file,
        )
        return {'templates': templates}
    except Exception as e:
        app.logger.error(f'Template list error: {e}')
        abort(500, description='Internal server error')


@app.route('/data_sources')
def list_data_sources():
    try:
        data_files = _list_allowed_files(
            app.config['DATA_SOURCES_DIR'],
            app.config['ALLOWED_DATA_EXTENSIONS'],
            report_generator.is_allowed_file,
        )
        return {'data_sources': data_files}
    except Exception as e:
        app.logger.error(f'Data source list error: {e}')
        abort(500, description='Internal server error')


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT)
