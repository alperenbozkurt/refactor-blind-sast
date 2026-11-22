import os
import csv
import json
from flask import Flask, request, send_file, abort
from jinja2 import Template

app = Flask(__name__)
app.config['TEMPLATE_DIR'] = './templates'
app.config['REPORT_OUTPUT_DIR'] = './reports'
app.config['DATA_SOURCES_DIR'] = './data_sources'


def _read_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def _read_csv(path):
    with open(path, 'r') as f:
        return list(csv.DictReader(f))


def _list_files(directory):
    """Return the names of all regular files directly inside ``directory``."""
    return [
        name for name in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, name))
    ]


class ReportGenerator:

    def __init__(self):
        for config_key in ('TEMPLATE_DIR', 'REPORT_OUTPUT_DIR', 'DATA_SOURCES_DIR'):
            os.makedirs(app.config[config_key], exist_ok=True)

    def load_template(self, template_name):
        template_path = os.path.join(app.config['TEMPLATE_DIR'], template_name)
        try:
            with open(template_path, 'r') as f:
                return Template(f.read())
        except Exception:
            return None

    def load_data_source(self, data_file):
        data_path = os.path.join(app.config['DATA_SOURCES_DIR'], data_file)
        try:
            if data_file.endswith('.json'):
                return _read_json(data_path)
            if data_file.endswith('.csv'):
                return _read_csv(data_path)
            return None
        except Exception:
            return None

    def generate_report(self, template_file, data_file, output_format='html'):
        template = self.load_template(template_file)
        data = self.load_data_source(data_file)
        if not template or not data:
            return None

        report_content = template.render(data=data)
        base_name = os.path.splitext(template_file)[0]
        output_filename = f'report_{base_name}.{output_format}'
        output_path = os.path.join(app.config['REPORT_OUTPUT_DIR'], output_filename)
        try:
            with open(output_path, 'w') as f:
                f.write(report_content)
            return output_path
        except Exception:
            return None


report_generator = ReportGenerator()


@app.route('/report', methods=['POST'])
def create_report():
    data = request.get_json()
    if not data or 'template' not in data or 'data_source' not in data:
        abort(400, description='Missing template or data_source')

    output_format = data.get('format', 'html')
    report_path = report_generator.generate_report(
        data['template'], data['data_source'], output_format
    )
    if report_path:
        return ({'status': 'success', 'report_path': os.path.basename(report_path)}, 201)
    return ({'error': 'Failed to generate report'}, 500)


@app.route('/report/download/<path:report_file>')
def download_report(report_file):
    report_path = os.path.join(app.config['REPORT_OUTPUT_DIR'], report_file)
    if not os.path.exists(report_path):
        abort(404, description='Report not found')
    try:
        return send_file(report_path, as_attachment=True)
    except Exception as e:
        abort(500, description=str(e))


@app.route('/templates')
def list_templates():
    try:
        return {'templates': _list_files(app.config['TEMPLATE_DIR'])}
    except Exception as e:
        abort(500, description=str(e))


@app.route('/data_sources')
def list_data_sources():
    try:
        return {'data_sources': _list_files(app.config['DATA_SOURCES_DIR'])}
    except Exception as e:
        abort(500, description=str(e))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
