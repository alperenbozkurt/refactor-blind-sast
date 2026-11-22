import csv
import os

from flask import Flask, abort, jsonify, render_template, request, send_file

app = Flask(__name__)
app.config['REPORT_TEMPLATES'] = os.path.join(os.path.dirname(__file__), 'templates')
app.config['DATA_SOURCES'] = os.path.join(os.path.dirname(__file__), 'data')
app.config['OUTPUT_DIR'] = os.path.join(os.path.dirname(__file__), 'reports')


class ReportGenerator:
    """Create text reports by combining a template file with CSV data."""

    def __init__(self):
        if not os.path.exists(app.config['OUTPUT_DIR']):
            os.makedirs(app.config['OUTPUT_DIR'])

    def load_template(self, template_name):
        """Return the contents of the named report template."""
        template_path = os.path.join(app.config['REPORT_TEMPLATES'], template_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f'Template {template_name} not found')
        with open(template_path, 'r') as f:
            return f.read()

    def load_data(self, data_file):
        """Return the rows of the named CSV data file as a list of dicts."""
        data_path = os.path.join(app.config['DATA_SOURCES'], data_file)
        if not os.path.exists(data_path):
            raise FileNotFoundError(f'Data file {data_file} not found')
        with open(data_path, 'r') as f:
            return list(csv.DictReader(f))

    def generate_report(self, template_name, data_file, output_name):
        """Render a report from a template and data file into the output directory."""
        try:
            template = self.load_template(template_name)
            data = self.load_data(data_file)
            report_content = template.format(data=data)
            output_path = os.path.join(app.config['OUTPUT_DIR'], output_name)
            with open(output_path, 'w') as f:
                f.write(report_content)
            return output_path
        except Exception as e:
            raise RuntimeError(f'Report generation failed: {str(e)}')


@app.route('/api/generate', methods=['POST'])
def generate_report():
    """Generate a report from the JSON request body and return its location."""
    try:
        data = request.get_json()
        template = data.get('template')
        data_file = data.get('data_file')
        output_name = data.get('output_name', 'report.txt')
        if not template or not data_file:
            return jsonify({'error': 'Missing template or data file'}), 400
        generator = ReportGenerator()
        report_path = generator.generate_report(template, data_file, output_name)
        return jsonify({
            'status': 'success',
            'report_path': report_path,
            'download_url': f'/api/download/{os.path.basename(report_path)}',
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<filename>')
def download_report(filename):
    """Send the requested report file back to the client as an attachment."""
    try:
        report_path = os.path.join(app.config['OUTPUT_DIR'], filename)
        if not os.path.exists(report_path):
            abort(404, 'Report not found')
        return send_file(report_path, as_attachment=True)
    except Exception as e:
        abort(500, str(e))


@app.route('/')
def index():
    """Render the home page listing the available templates and data files."""
    templates = []
    data_files = []
    try:
        templates = os.listdir(app.config['REPORT_TEMPLATES'])
        data_files = [
            f for f in os.listdir(app.config['DATA_SOURCES'])
            if f.endswith('.csv')
        ]
    except Exception:
        pass
    return render_template('index.html', templates=templates, data_files=data_files)


if __name__ == '__main__':
    for config_key in ('REPORT_TEMPLATES', 'DATA_SOURCES', 'OUTPUT_DIR'):
        os.makedirs(app.config[config_key], exist_ok=True)
    with open(os.path.join(app.config['REPORT_TEMPLATES'], 'default.tpl'), 'w') as f:
        f.write('Report Data:\n\n{data}')
    with open(os.path.join(app.config['DATA_SOURCES'], 'sample.csv'), 'w') as f:
        f.write('id,name,value\n1,Test,100\n2,Example,200')
    app.run(host='0.0.0.0', port=5000)
