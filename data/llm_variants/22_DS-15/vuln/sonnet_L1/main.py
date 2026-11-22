import os
import csv
from flask import Flask, request, send_file, render_template, abort, jsonify

BASE_DIR = os.path.dirname(__file__)

app = Flask(__name__)
app.config['REPORT_TEMPLATES'] = os.path.join(BASE_DIR, 'templates')
app.config['DATA_SOURCES'] = os.path.join(BASE_DIR, 'data')
app.config['OUTPUT_DIR'] = os.path.join(BASE_DIR, 'reports')

DEFAULT_OUTPUT_NAME = 'report.txt'
DEFAULT_TEMPLATE_CONTENT = 'Report Data:\n\n{data}'
SAMPLE_DATA_CONTENT = 'id,name,value\n1,Test,100\n2,Example,200'


def _config_path(config_key, filename):
    """Join a configured directory with a file name."""
    return os.path.join(app.config[config_key], filename)


class ReportGenerator:
    """Generates text reports from a template and a CSV data source."""

    def __init__(self):
        if not os.path.exists(app.config['OUTPUT_DIR']):
            os.makedirs(app.config['OUTPUT_DIR'])

    def load_template(self, template_name):
        template_path = _config_path('REPORT_TEMPLATES', template_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f'Template {template_name} not found')
        with open(template_path, 'r') as f:
            return f.read()

    def load_data(self, data_file):
        data_path = _config_path('DATA_SOURCES', data_file)
        if not os.path.exists(data_path):
            raise FileNotFoundError(f'Data file {data_file} not found')
        with open(data_path, 'r') as f:
            return list(csv.DictReader(f))

    def generate_report(self, template_name, data_file, output_name):
        try:
            template = self.load_template(template_name)
            data = self.load_data(data_file)
            report_content = template.format(data=data)
            output_path = _config_path('OUTPUT_DIR', output_name)
            with open(output_path, 'w') as f:
                f.write(report_content)
            return output_path
        except Exception as e:
            raise RuntimeError(f'Report generation failed: {str(e)}')


@app.route('/api/generate', methods=['POST'])
def generate_report():
    try:
        payload = request.get_json()
        template = payload.get('template')
        data_file = payload.get('data_file')
        output_name = payload.get('output_name', DEFAULT_OUTPUT_NAME)

        if not template or not data_file:
            return (jsonify({'error': 'Missing template or data file'}), 400)

        generator = ReportGenerator()
        report_path = generator.generate_report(template, data_file, output_name)
        return jsonify({
            'status': 'success',
            'report_path': report_path,
            'download_url': f'/api/download/{os.path.basename(report_path)}',
        })
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)


@app.route('/api/download/<filename>')
def download_report(filename):
    try:
        report_path = _config_path('OUTPUT_DIR', filename)
        if not os.path.exists(report_path):
            abort(404, 'Report not found')
        return send_file(report_path, as_attachment=True)
    except Exception as e:
        abort(500, str(e))


@app.route('/')
def index():
    templates = []
    data_files = []
    try:
        templates = os.listdir(app.config['REPORT_TEMPLATES'])
        data_files = [
            name for name in os.listdir(app.config['DATA_SOURCES'])
            if name.endswith('.csv')
        ]
    except Exception:
        pass
    return render_template('index.html', templates=templates, data_files=data_files)


def _write_text_file(path, content):
    with open(path, 'w') as f:
        f.write(content)


def _prepare_environment():
    """Create working directories and sample files for local runs."""
    os.makedirs(app.config['REPORT_TEMPLATES'], exist_ok=True)
    os.makedirs(app.config['DATA_SOURCES'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_DIR'], exist_ok=True)
    _write_text_file(_config_path('REPORT_TEMPLATES', 'default.tpl'), DEFAULT_TEMPLATE_CONTENT)
    _write_text_file(_config_path('DATA_SOURCES', 'sample.csv'), SAMPLE_DATA_CONTENT)


if __name__ == '__main__':
    _prepare_environment()
    app.run(host='0.0.0.0', port=5000)
