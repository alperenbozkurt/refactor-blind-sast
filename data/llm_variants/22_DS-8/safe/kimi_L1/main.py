"""Report generation service.

Renders Jinja2 templates with JSON or CSV data sources into report files
that can be created, listed and downloaded through the Flask API.
"""

import csv
import json
import os

from flask import Flask, abort, request, send_file
from jinja2 import Template, escape
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['TEMPLATE_DIR'] = os.path.abspath('./templates')
app.config['REPORT_OUTPUT_DIR'] = os.path.abspath('./reports')
app.config['DATA_SOURCES_DIR'] = os.path.abspath('./data_sources')
app.config['ALLOWED_TEMPLATE_EXT'] = '.html'
app.config['ALLOWED_DATA_EXTENSIONS'] = {'.json', '.csv'}


class ReportGenerator:
    """Validate templates and data sources, then render them into reports."""

    def __init__(self):
        for directory in (
            app.config['TEMPLATE_DIR'],
            app.config['REPORT_OUTPUT_DIR'],
            app.config['DATA_SOURCES_DIR'],
        ):
            os.makedirs(directory, exist_ok=True)

    def is_safe_path(self, base, path):
        """Return True only if `path` resolves to a location inside `base`."""
        resolved_base = os.path.abspath(base)
        resolved_path = os.path.abspath(path)
        return resolved_path.startswith(resolved_base + os.sep)

    def is_allowed_file(self, filename, allowed_extensions):
        """Return True if `filename` has an allowed extension and contains
        no path-traversal or home-directory markers."""
        if not filename:
            return False
        has_allowed_extension = any(
            filename.endswith(extension) for extension in allowed_extensions
        )
        if not has_allowed_extension:
            return False
        if '../' in filename or '~' in filename:
            return False
        return True

    def load_template(self, template_name):
        """Load an allowed template file, escaping its raw contents."""
        allowed_extensions = {app.config['ALLOWED_TEMPLATE_EXT']}
        if not self.is_allowed_file(template_name, allowed_extensions):
            return None
        template_path = os.path.join(app.config['TEMPLATE_DIR'], template_name)
        if not self.is_safe_path(app.config['TEMPLATE_DIR'], template_path):
            return None
        try:
            with open(template_path, 'r') as file_obj:
                return Template(escape(file_obj.read()))
        except Exception as e:
            app.logger.error(f'Template load error: {e}')
            return None

    def load_data_source(self, data_file):
        """Load an allowed JSON or CSV data file with escaped values."""
        if not self.is_allowed_file(data_file, app.config['ALLOWED_DATA_EXTENSIONS']):
            return None
        data_path = os.path.join(app.config['DATA_SOURCES_DIR'], data_file)
        if not self.is_safe_path(app.config['DATA_SOURCES_DIR'], data_path):
            return None
        try:
            if data_file.endswith('.json'):
                return self._load_json_data(data_path)
            if data_file.endswith('.csv'):
                return self._load_csv_data(data_path)
            return None
        except Exception as e:
            app.logger.error(f'Data load error: {e}')
            return None

    def generate_report(self, template_file, data_file, output_format='html'):
        """Render `template_file` with `data_file` into the reports directory."""
        if output_format not in {'html', 'txt'}:
            return None
        template = self.load_template(template_file)
        data = self.load_data_source(data_file)
        if not template or not data:
            return None
        try:
            report_content = template.render(data=data)
            template_stem = os.path.splitext(template_file)[0]
            safe_filename = secure_filename(f'report_{template_stem}.{output_format}')
            output_path = os.path.join(app.config['REPORT_OUTPUT_DIR'], safe_filename)
            if not self.is_safe_path(app.config['REPORT_OUTPUT_DIR'], output_path):
                return None
            with open(output_path, 'w') as file_obj:
                file_obj.write(report_content)
            return output_path
        except Exception as e:
            app.logger.error(f'Report generation error: {e}')
            return None

    @staticmethod
    def _escape_values(record):
        """Return a copy of `record` with every value HTML-escaped."""
        return {key: escape(str(value)) for key, value in record.items()}

    def _load_json_data(self, data_path):
        with open(data_path, 'r') as file_obj:
            data = json.load(file_obj)
        if isinstance(data, dict):
            return self._escape_values(data)
        if isinstance(data, list):
            return [self._escape_values(item) for item in data]
        return data

    def _load_csv_data(self, data_path):
        with open(data_path, 'r') as file_obj:
            return [self._escape_values(row) for row in csv.DictReader(file_obj)]


report_generator = ReportGenerator()


@app.route('/report', methods=['POST'])
def create_report():
    data = request.get_json()
    if not data or 'template' not in data or 'data_source' not in data:
        abort(400, description='Invalid request')
    if not isinstance(data['template'], str) or not isinstance(data['data_source'], str):
        abort(400, description='Invalid input type')
    output_format = data.get('format', 'html')
    report_path = report_generator.generate_report(
        data['template'], data['data_source'], output_format
    )
    if report_path:
        return {'status': 'success', 'report_path': os.path.basename(report_path)}, 201
    return {'error': 'Report generation failed'}, 500


@app.route('/report/download/<path:report_file>')
def download_report(report_file):
    if not report_generator.is_allowed_file(report_file, {'.html', '.txt'}):
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
        template_dir = app.config['TEMPLATE_DIR']
        allowed_extensions = {app.config['ALLOWED_TEMPLATE_EXT']}
        templates = [
            filename
            for filename in os.listdir(template_dir)
            if os.path.isfile(os.path.join(template_dir, filename))
            and report_generator.is_allowed_file(filename, allowed_extensions)
        ]
        return {'templates': templates}
    except Exception as e:
        app.logger.error(f'Template list error: {e}')
        abort(500, description='Internal server error')


@app.route('/data_sources')
def list_data_sources():
    try:
        data_sources_dir = app.config['DATA_SOURCES_DIR']
        allowed_extensions = app.config['ALLOWED_DATA_EXTENSIONS']
        data_files = [
            filename
            for filename in os.listdir(data_sources_dir)
            if os.path.isfile(os.path.join(data_sources_dir, filename))
            and report_generator.is_allowed_file(filename, allowed_extensions)
        ]
        return {'data_sources': data_files}
    except Exception as e:
        app.logger.error(f'Data source list error: {e}')
        abort(500, description='Internal server error')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
