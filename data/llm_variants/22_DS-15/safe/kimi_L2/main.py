"""Report generation web service.

A small Flask application that renders plain-text reports from ``.tpl``
templates and ``.csv`` data files, and exposes the generated reports for
download.
"""

import csv
import os

from flask import Flask, abort, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

TEMPLATE_DIR_NAME = 'templates'
DATA_DIR_NAME = 'data'
OUTPUT_DIR_NAME = 'reports'

TEMPLATE_EXTENSION = '.tpl'
DATA_EXTENSION = '.csv'
OUTPUT_EXTENSION = '.txt'

DIRECTORY_PERMISSIONS = 0o750
FILE_PERMISSIONS = 0o640

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000

DEFAULT_OUTPUT_NAME = 'report.txt'

SAMPLE_TEMPLATE_NAME = 'default.tpl'
SAMPLE_TEMPLATE_CONTENT = 'Report Data:\n\n{data}'

SAMPLE_DATA_NAME = 'sample.csv'
SAMPLE_DATA_CONTENT = 'id,name,value\n1,Test,100\n2,Example,200'

app = Flask(__name__)


def configure_app(application):
    """Populate the Flask config with the locations used by the service."""
    application.config['REPORT_TEMPLATES'] = os.path.abspath(
        os.path.join(BASE_DIR, TEMPLATE_DIR_NAME))
    application.config['DATA_SOURCES'] = os.path.abspath(
        os.path.join(BASE_DIR, DATA_DIR_NAME))
    application.config['OUTPUT_DIR'] = os.path.abspath(
        os.path.join(BASE_DIR, OUTPUT_DIR_NAME))
    application.config['ALLOWED_EXTENSIONS'] = {
        TEMPLATE_EXTENSION, DATA_EXTENSION, OUTPUT_EXTENSION,
    }


configure_app(app)


class ReportGenerator:
    """Builds report files from template files and CSV data sources."""

    def __init__(self):
        os.makedirs(app.config['OUTPUT_DIR'], exist_ok=True)

    def is_safe_path(self, base_path, requested_path):
        base_path = os.path.abspath(base_path)
        requested_path = os.path.abspath(requested_path)
        return requested_path.startswith(base_path + os.sep)

    def is_allowed_file(self, filename, allowed_extensions):
        if not filename or not isinstance(filename, str):
            return False
        if not any(filename.endswith(ext) for ext in allowed_extensions):
            return False
        if '../' in filename or '~' in filename:
            return False
        return True

    def _resolve_existing_path(self, base_dir, filename, allowed_extensions,
                               invalid_name_message, invalid_path_message,
                               not_found_message):
        """Validate ``filename`` under ``base_dir`` and return its full path."""
        if not self.is_allowed_file(filename, allowed_extensions):
            raise ValueError(invalid_name_message)
        file_path = os.path.join(base_dir, filename)
        if not self.is_safe_path(base_dir, file_path):
            raise ValueError(invalid_path_message)
        if not os.path.exists(file_path):
            raise FileNotFoundError(not_found_message)
        return file_path

    def load_template(self, template_name):
        template_path = self._resolve_existing_path(
            app.config['REPORT_TEMPLATES'], template_name, {TEMPLATE_EXTENSION},
            'Invalid template name', 'Invalid template path',
            'Template not found')
        with open(template_path, 'r') as template_file:
            return template_file.read()

    def load_data(self, data_file):
        data_path = self._resolve_existing_path(
            app.config['DATA_SOURCES'], data_file, {DATA_EXTENSION},
            'Invalid data file name', 'Invalid data path',
            'Data file not found')
        with open(data_path, 'r') as csv_file:
            reader = csv.DictReader(csv_file)
            return list(reader)

    def generate_report(self, template_name, data_file, output_name):
        try:
            if not self.is_allowed_file(output_name, {OUTPUT_EXTENSION}):
                raise ValueError('Invalid output file name')
            template = self.load_template(template_name)
            data = self.load_data(data_file)
            report_content = template.format(data=data)
            output_path = os.path.join(
                app.config['OUTPUT_DIR'], secure_filename(output_name))
            if not self.is_safe_path(app.config['OUTPUT_DIR'], output_path):
                raise ValueError('Invalid output path')
            with open(output_path, 'w') as output_file:
                output_file.write(report_content)
            return output_path
        except Exception as e:
            raise RuntimeError(f'Report generation failed: {str(e)}')


def _error_response(message, status_code):
    """Build a JSON error response tuple for the API endpoints."""
    return (jsonify({'error': message}), status_code)


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
            'download_url': f'/api/download/{report_name}',
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


def list_files_with_extension(directory, extension):
    """Return the regular files in ``directory`` ending with ``extension``."""
    return [
        entry
        for entry in os.listdir(directory)
        if entry.endswith(extension)
        and os.path.isfile(os.path.join(directory, entry))
    ]


@app.route('/')
def index():
    templates = []
    data_files = []
    try:
        templates = list_files_with_extension(
            app.config['REPORT_TEMPLATES'], TEMPLATE_EXTENSION)
        data_files = list_files_with_extension(
            app.config['DATA_SOURCES'], DATA_EXTENSION)
    except Exception as e:
        app.logger.error(f'Directory listing error: {e}')
    return render_template('index.html', templates=templates, data_files=data_files)


def create_directories():
    """Ensure the template, data and output directories exist."""
    for directory in (
        app.config['REPORT_TEMPLATES'],
        app.config['DATA_SOURCES'],
        app.config['OUTPUT_DIR'],
    ):
        os.makedirs(directory, mode=DIRECTORY_PERMISSIONS, exist_ok=True)


def create_sample_file(file_path, content, label):
    """Write a sample file with restricted permissions, logging failures."""
    try:
        with open(file_path, 'w') as sample_file:
            sample_file.write(content)
        os.chmod(file_path, FILE_PERMISSIONS)
    except Exception as e:
        app.logger.error(f'Error creating sample {label}: {e}')


def create_sample_files():
    """Create the sample template and data file used for a first run."""
    create_sample_file(
        os.path.join(app.config['REPORT_TEMPLATES'], SAMPLE_TEMPLATE_NAME),
        SAMPLE_TEMPLATE_CONTENT,
        'template',
    )
    create_sample_file(
        os.path.join(app.config['DATA_SOURCES'], SAMPLE_DATA_NAME),
        SAMPLE_DATA_CONTENT,
        'data',
    )


def main():
    """Command-line entry point: bootstrap the workspace and run the server."""
    create_directories()
    create_sample_files()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
