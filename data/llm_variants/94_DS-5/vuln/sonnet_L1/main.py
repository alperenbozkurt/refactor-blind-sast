from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
import os
import datetime

DEFAULT_TEMPLATE = 'Custom Report'

REPORT_TEMPLATES = {
    'sales': 'Sales report for {period}',
    'inventory': 'Inventory status as of {date}',
}

HOME_PAGE_HTML = (
    '\n'
    '    <h1>Corporate Report Generator</h1>\n'
    '    <form action="/generate" method="post">\n'
    '        Report Type: \n'
    '        <select name="report_type">\n'
    '            <option value="sales">Sales</option>\n'
    '            <option value="inventory">Inventory</option>\n'
    '        </select><br>\n'
    '        Custom Logic (Python):<br>\n'
    '        <textarea name="custom_logic" rows=4 cols=50>\n'
    "period = 'Q2 2023'\n"
    "date = datetime.datetime.now().strftime('%Y-%m-%d')\n"
    '        </textarea><br>\n'
    '        <input type="submit" value="Generate Report">\n'
    '    </form>\n'
    '    '
)


class ReportGenerator:

    def __init__(self):
        self.report_templates = dict(REPORT_TEMPLATES)

    def generate_report(self, report_type, custom_logic):
        template = self.report_templates.get(report_type, DEFAULT_TEMPLATE)
        try:
            # NOTE: behaviour intentionally preserved: user-supplied code is
            # executed and the template is evaluated as an f-string.
            exec(custom_logic, globals(), locals())
            return eval(f'f"""{template}"""')
        except Exception as e:
            return f'Report generation failed: {str(e)}'


report_engine = ReportGenerator()


@view_config(route_name='home', renderer='string')
def home_view(request):
    return HOME_PAGE_HTML


@view_config(route_name='generate', request_method='POST', renderer='string')
def generate_view(request):
    report_type = request.POST['report_type']
    custom_logic = request.POST['custom_logic']
    report = report_engine.generate_report(report_type, custom_logic)
    return (
        f'\n'
        f'    <h2>Generated Report</h2>\n'
        f'    <pre>{report}</pre>\n'
        f'    <a href="/">Back</a>\n'
        f'    '
    )


def make_app():
    with Configurator() as config:
        config.add_route('home', '/')
        config.add_route('generate', '/generate')
        config.scan()
        return config.make_wsgi_app()


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    app = make_app()
    server = make_server('0.0.0.0', 6543, app)
    server.serve_forever()
