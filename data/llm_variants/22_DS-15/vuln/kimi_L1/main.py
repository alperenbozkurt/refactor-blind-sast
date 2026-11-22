"""Flask application for generating and downloading text reports.

Reports are rendered from plain-text templates stored in the templates
directory and CSV data files stored in the data directory. Generated
reports are written to the reports directory and served through the API.
"""

import csv
import os

from flask import Flask, abort, jsonify, render_template, request, send_file

app = Flask(__name__)
app.config['REPORT_TEMPLATES'] = os.path.join(os.path.dirname(__file__), 'templates')
app.config['DATA_SOURCES'] = os.path.join(os.path.dirname(__file__), 'data')
app.config['OUTPUT_DIR'] = os.path.join(os.path.dirname(__file__), 'reports')


class ReportGenerator:
    """Render text reports from string templates and CSV data files."""

    def __init__(self):
        if not os.path.exists(app.config['OUTPUT_DIR']):
            os.makedirs(app.config['OUTPUT_DIR'])

    def load_template(self, template_name):
        """Return the contents of the template with the given name."""
        template_path = os.path.join(app.config['REPORT_TEMPLATES'], template_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f'Template {template_name} not found')
        with open(template_path, 'r') as template_file:
            return template_file.read()

    def load_data(self, data_file):
        """Return the rows of the given CSV file as a list of dictionaries."""
        data_path = os.path.join(app.config['DATA_SOURCES'], data_file)
        if not os.path.exists(data_path):
            raise FileNotFoundError(f'Data file {data_file} not found')
        with open(data_path, 'r') as data_source:
            return list(csv.DictReader(data_source))

    def generate_report(self, template_name, data_file, output_name):
        """Render a report and return the path of the generated file."""
        try:
            template = self.load_template(template_name)
            data = self.load_data(data_file)
            report_content = template.format(data=data)
            output_path = os.path.join(app.config['OUTPUT_DIR'], output_name)
            with open(output_path, 'w') as output_file:
                output_file.write(report_content)
            return output_path
        except Exception as exc:
            raise RuntimeError(f'Report generation failed: {str(exc)}')


@app.route('/api/generate', methods=['POST'])
def generate_report():
    """Generate a report based on the JSON payload of the request."""
    try:
        payload = request.get_json()
        template = payload.get('template')
        data_file = payload.get('data_file')
        output_name = payload.get('output_name', 'report.txt')
        if not template or not data_file:
            return jsonify({'error': 'Missing template or data file'}), 400
        generator = ReportGenerator()
        report_path = generator.generate_report(template, data_file, output_name)
        return jsonify({
            'status': 'success',
            'report_path': report_path,
            'download_url': f'/api/download/{os.path.basename(report_path)}',
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/api/download/<filename>')
def download_report(filename):
    """Send the requested report file to the client as an attachment."""
    try:
        report_path = os.path.join(app.config['OUTPUT_DIR'], filename)
        if not os.path.exists(report_path):
            abort(404, 'Report not found')
        return send_file(report_path, as_attachment=True)
    except Exception as exc:
        abort(500, str(exc))


@app.route('/')
def index():
    """Render the index page with the available templates and data files."""
    templates = []
    data_files = []
    try:
        templates = os.listdir(app.config['REPORT_TEMPLATES'])
        data_files = [
            filename
            for filename in os.listdir(app.config['DATA_SOURCES'])
            if filename.endswith('.csv')
        ]
    except Exception:
        pass
    return render_template('index.html', templates=templates, data_files=data_files)


if __name__ == '__main__':
    os.makedirs(app.config['REPORT_TEMPLATES'], exist_ok=True)
    os.makedirs(app.config['DATA_SOURCES'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_DIR'], exist_ok=True)

    default_template_path = os.path.join(app.config['REPORT_TEMPLATES'], 'default.tpl')
    with open(default_template_path, 'w') as template_file:
        template_file.write('Report Data:\n\n{data}')

    sample_data_path = os.path.join(app.config['DATA_SOURCES'], 'sample.csv')
    with open(sample_data_path, 'w') as data_file:
        data_file.write('id,name,value\n1,Test,100\n2,Example,200')

    app.run(host='0.0.0.0', port=5000)
