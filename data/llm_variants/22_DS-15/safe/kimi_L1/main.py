"""Flask application for generating text reports from templates and CSV data."""

import csv
import os

from flask import Flask, abort, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

_BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app.config['REPORT_TEMPLATES'] = os.path.join(_BASE_DIR, 'templates')
app.config['DATA_SOURCES'] = os.path.join(_BASE_DIR, 'data')
app.config['OUTPUT_DIR'] = os.path.join(_BASE_DIR, 'reports')
app.config['ALLOWED_EXTENSIONS'] = {'.tpl', '.csv', '.txt'}


class ReportGenerator:
    """Builds reports by formatting a template with rows from a CSV data file."""

    def __init__(self):
        os.makedirs(app.config['OUTPUT_DIR'], exist_ok=True)

    def is_safe_path(self, base_path, requested_path):
        """Return True only when requested_path resides inside base_path.

        Appending os.sep stops sibling directories that merely share a name
        prefix (e.g. ``data_evil`` next to ``data``) from being accepted.
        """
        base_path = os.path.abspath(base_path)
        requested_path = os.path.abspath(requested_path)
        return requested_path.startswith(base_path + os.sep)

    def is_allowed_file(self, filename, allowed_extensions):
        """Return True when filename is a non-empty string with an allowed
        extension and contains no traversal or home-directory tokens."""
        return (
            bool(filename)
            and isinstance(filename, str)
            and any(filename.endswith(ext) for ext in allowed_extensions)
            and '../' not in filename
            and '~' not in filename
        )

    def _resolve_existing_file(self, base_dir, filename, allowed_extensions,
                               invalid_name_msg, invalid_path_msg,
                               not_found_msg):
        """Validate filename and return its path inside base_dir.

        Raises ValueError (twice, with distinct messages) and
        FileNotFoundError exactly as the per-resource checks require.
        """
        if not self.is_allowed_file(filename, allowed_extensions):
            raise ValueError(invalid_name_msg)
        file_path = os.path.join(base_dir, filename)
        if not self.is_safe_path(base_dir, file_path):
            raise ValueError(invalid_path_msg)
        if not os.path.exists(file_path):
            raise FileNotFoundError(not_found_msg)
        return file_path

    def load_template(self, template_name):
        """Read and return the contents of a .tpl template file."""
        template_path = self._resolve_existing_file(
            app.config['REPORT_TEMPLATES'], template_name, {'.tpl'},
            'Invalid template name', 'Invalid template path',
            'Template not found')
        with open(template_path, 'r') as f:
            return f.read()

    def load_data(self, data_file):
        """Read a .csv data file and return its rows as a list of dicts."""
        data_path = self._resolve_existing_file(
            app.config['DATA_SOURCES'], data_file, {'.csv'},
            'Invalid data file name', 'Invalid data path',
            'Data file not found')
        with open(data_path, 'r') as f:
            return list(csv.DictReader(f))

    def generate_report(self, template_name, data_file, output_name):
        """Render template_name with the rows of data_file into output_name.

        Every failure is re-raised as a RuntimeError with a uniform message.
        """
        try:
            if not self.is_allowed_file(output_name, {'.txt'}):
                raise ValueError('Invalid output file name')
            template = self.load_template(template_name)
            data = self.load_data(data_file)
            report_content = template.format(data=data)
            output_path = os.path.join(app.config['OUTPUT_DIR'],
                                       secure_filename(output_name))
            if not self.is_safe_path(app.config['OUTPUT_DIR'], output_path):
                raise ValueError('Invalid output path')
            with open(output_path, 'w') as f:
                f.write(report_content)
            return output_path
        except Exception as e:
            raise RuntimeError(f'Report generation failed: {str(e)}')


@app.route('/api/generate', methods=['POST'])
def generate_report():
    """Create a report from a template and a data file supplied as JSON."""
    try:
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify({'error': 'Invalid request'}), 400
        template = data.get('template')
        data_file = data.get('data_file')
        output_name = secure_filename(data.get('output_name', 'report.txt'))
        if not template or not data_file:
            return jsonify({'error': 'Missing template or data file'}), 400
        generator = ReportGenerator()
        report_path = generator.generate_report(template, data_file,
                                                output_name)
        report_name = os.path.basename(report_path)
        return jsonify({
            'status': 'success',
            'report_path': report_name,
            'download_url': f'/api/download/{report_name}',
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        app.logger.error(f'Report generation error: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/download/<filename>')
def download_report(filename):
    """Send a previously generated report back to the client as an attachment."""
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


def _list_files_with_extension(directory, extension):
    """Return the regular files in directory whose names end with extension."""
    return [
        name
        for name in os.listdir(directory)
        if name.endswith(extension)
        and os.path.isfile(os.path.join(directory, name))
    ]


@app.route('/')
def index():
    """Render the main page with the available templates and data files."""
    templates = []
    data_files = []
    try:
        templates = _list_files_with_extension(
            app.config['REPORT_TEMPLATES'], '.tpl')
        data_files = _list_files_with_extension(
            app.config['DATA_SOURCES'], '.csv')
    except Exception as e:
        app.logger.error(f'Directory listing error: {e}')
    return render_template('index.html', templates=templates,
                           data_files=data_files)


def _create_sample_file(path, content, description):
    """Write a sample file with owner-only permissions, logging any failure."""
    try:
        with open(path, 'w') as f:
            f.write(content)
        os.chmod(path, 0o640)
    except Exception as e:
        app.logger.error(f'Error creating {description}: {e}')


if __name__ == '__main__':
    for directory in (app.config['REPORT_TEMPLATES'],
                      app.config['DATA_SOURCES'],
                      app.config['OUTPUT_DIR']):
        os.makedirs(directory, mode=0o750, exist_ok=True)

    _create_sample_file(
        os.path.join(app.config['REPORT_TEMPLATES'], 'default.tpl'),
        'Report Data:\n\n{data}',
        'sample template')
    _create_sample_file(
        os.path.join(app.config['DATA_SOURCES'], 'sample.csv'),
        'id,name,value\n1,Test,100\n2,Example,200',
        'sample data')

    app.run(host='0.0.0.0', port=5000)
