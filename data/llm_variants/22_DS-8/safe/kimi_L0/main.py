import csv
import json
import os

from flask import Flask, abort, request, send_file
from jinja2 import Template, escape
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.update(
    TEMPLATE_DIR=os.path.abspath('./templates'),
    REPORT_OUTPUT_DIR=os.path.abspath('./reports'),
    DATA_SOURCES_DIR=os.path.abspath('./data_sources'),
    ALLOWED_TEMPLATE_EXT='.html',
    ALLOWED_DATA_EXTENSIONS={'.json', '.csv'},
)


class ReportGenerator:
    """Loads templates and data sources and renders them into report files."""

    def __init__(self):
        for config_key in ('TEMPLATE_DIR', 'REPORT_OUTPUT_DIR', 'DATA_SOURCES_DIR'):
            os.makedirs(app.config[config_key], exist_ok=True)

    def is_safe_path(self, base, path):
        base = os.path.abspath(base)
        path = os.path.abspath(path)
        return path.startswith(base + os.sep)

    def is_allowed_file(self, filename, allowed_extensions):
        return bool(
            filename
            and any(filename.endswith(ext) for ext in allowed_extensions)
            and '../' not in filename
            and '~' not in filename
        )

    @staticmethod
    def _escape_mapping(mapping):
        return {key: escape(str(value)) for key, value in mapping.items()}

    def _list_allowed_files(self, directory, allowed_extensions):
        return [
            filename
            for filename in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, filename))
            and self.is_allowed_file(filename, allowed_extensions)
        ]

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
            if data_file.endswith('.json'):
                with open(data_path, 'r') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return self._escape_mapping(data)
                if isinstance(data, list):
                    return [self._escape_mapping(item) for item in data]
                return data
            if data_file.endswith('.csv'):
                with open(data_path, 'r') as f:
                    return [self._escape_mapping(row) for row in csv.DictReader(f)]
            return None
        except Exception as e:
            app.logger.error(f'Data load error: {e}')
            return None

    def generate_report(self, template_file, data_file, output_format='html'):
        if output_format not in {'html', 'txt'}:
            return None
        template = self.load_template(template_file)
        data = self.load_data_source(data_file)
        if not template or not data:
            return None
        try:
            report_content = template.render(data=data)
            report_name = os.path.splitext(template_file)[0]
            safe_filename = secure_filename(f'report_{report_name}.{output_format}')
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


@app.route('/report', methods=['POST'])
def create_report():
    data = request.get_json()
    if not data or 'template' not in data or 'data_source' not in data:
        abort(400, description='Invalid request')
    if not isinstance(data['template'], str) or not isinstance(data['data_source'], str):
        abort(400, description='Invalid input type')
    report_path = report_generator.generate_report(
        data['template'], data['data_source'], data.get('format', 'html')
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
        templates = report_generator._list_allowed_files(
            app.config['TEMPLATE_DIR'], {app.config['ALLOWED_TEMPLATE_EXT']}
        )
        return {'templates': templates}
    except Exception as e:
        app.logger.error(f'Template list error: {e}')
        abort(500, description='Internal server error')


@app.route('/data_sources')
def list_data_sources():
    try:
        data_files = report_generator._list_allowed_files(
            app.config['DATA_SOURCES_DIR'], app.config['ALLOWED_DATA_EXTENSIONS']
        )
        return {'data_sources': data_files}
    except Exception as e:
        app.logger.error(f'Data source list error: {e}')
        abort(500, description='Internal server error')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
