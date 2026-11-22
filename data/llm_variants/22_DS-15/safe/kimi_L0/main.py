import csv
import os

from flask import Flask, abort, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['REPORT_TEMPLATES'] = os.path.join(BASE_DIR, 'templates')
app.config['DATA_SOURCES'] = os.path.join(BASE_DIR, 'data')
app.config['OUTPUT_DIR'] = os.path.join(BASE_DIR, 'reports')
app.config['ALLOWED_EXTENSIONS'] = {'.tpl', '.csv', '.txt'}


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
        if not any(filename.endswith(ext) for ext in allowed_extensions):
            return False
        return '../' not in filename and '~' not in filename

    def _resolve_existing_path(self, filename, allowed_extensions, base_dir,
                               invalid_name_msg, invalid_path_msg, not_found_msg):
        if not self.is_allowed_file(filename, allowed_extensions):
            raise ValueError(invalid_name_msg)
        file_path = os.path.join(base_dir, filename)
        if not self.is_safe_path(base_dir, file_path):
            raise ValueError(invalid_path_msg)
        if not os.path.exists(file_path):
            raise FileNotFoundError(not_found_msg)
        return file_path

    def load_template(self, template_name):
        template_path = self._resolve_existing_path(
            template_name,
            {'.tpl'},
            app.config['REPORT_TEMPLATES'],
            'Invalid template name',
            'Invalid template path',
            'Template not found',
        )
        with open(template_path, 'r') as f:
            return f.read()

    def load_data(self, data_file):
        data_path = self._resolve_existing_path(
            data_file,
            {'.csv'},
            app.config['DATA_SOURCES'],
            'Invalid data file name',
            'Invalid data path',
            'Data file not found',
        )
        with open(data_path, 'r') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def generate_report(self, template_name, data_file, output_name):
        try:
            if not self.is_allowed_file(output_name, {'.txt'}):
                raise ValueError('Invalid output file name')
            template = self.load_template(template_name)
            data = self.load_data(data_file)
            report_content = template.format(data=data)
            output_path = os.path.join(app.config['OUTPUT_DIR'], secure_filename(output_name))
            if not self.is_safe_path(app.config['OUTPUT_DIR'], output_path):
                raise ValueError('Invalid output path')
            with open(output_path, 'w') as f:
                f.write(report_content)
            return output_path
        except Exception as e:
            raise RuntimeError(f'Report generation failed: {str(e)}')


@app.route('/api/generate', methods=['POST'])
def generate_report():
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
        report_path = generator.generate_report(template, data_file, output_name)
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
    def list_files(directory, extension):
        return [
            name for name in os.listdir(directory)
            if name.endswith(extension) and os.path.isfile(os.path.join(directory, name))
        ]

    templates = []
    data_files = []
    try:
        templates = list_files(app.config['REPORT_TEMPLATES'], '.tpl')
        data_files = list_files(app.config['DATA_SOURCES'], '.csv')
    except Exception as e:
        app.logger.error(f'Directory listing error: {e}')
    return render_template('index.html', templates=templates, data_files=data_files)


if __name__ == '__main__':
    for directory in (
        app.config['REPORT_TEMPLATES'],
        app.config['DATA_SOURCES'],
        app.config['OUTPUT_DIR'],
    ):
        os.makedirs(directory, mode=0o750, exist_ok=True)

    template_path = os.path.join(app.config['REPORT_TEMPLATES'], 'default.tpl')
    try:
        with open(template_path, 'w') as f:
            f.write('Report Data:\n\n{data}')
        os.chmod(template_path, 0o640)
    except Exception as e:
        app.logger.error(f'Error creating sample template: {e}')

    data_path = os.path.join(app.config['DATA_SOURCES'], 'sample.csv')
    try:
        with open(data_path, 'w') as f:
            f.write('id,name,value\n1,Test,100\n2,Example,200')
        os.chmod(data_path, 0o640)
    except Exception as e:
        app.logger.error(f'Error creating sample data: {e}')

    app.run(host='0.0.0.0', port=5000)
