"""Corporate Report Generator.

A minimal Pyramid web application that renders report templates whose
placeholders are populated by user-supplied Python snippets.
"""

import datetime
import os

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

# --- Report configuration -------------------------------------------------

DEFAULT_REPORT_TEMPLATES = {
    'sales': 'Sales report for {period}',
    'inventory': 'Inventory status as of {date}',
}
FALLBACK_REPORT_TEMPLATE = 'Custom Report'
REPORT_FAILURE_MESSAGE = 'Report generation failed: {error}'

# --- Form field names ------------------------------------------------------

FORM_FIELD_REPORT_TYPE = 'report_type'
FORM_FIELD_CUSTOM_LOGIC = 'custom_logic'

# --- Page templates --------------------------------------------------------

HOME_PAGE = """
    <h1>Corporate Report Generator</h1>
    <form action="/generate" method="post">
        Report Type: 
        <select name="report_type">
            <option value="sales">Sales</option>
            <option value="inventory">Inventory</option>
        </select><br>
        Custom Logic (Python):<br>
        <textarea name="custom_logic" rows=4 cols=50>
period = 'Q2 2023'
date = datetime.datetime.now().strftime('%Y-%m-%d')
        </textarea><br>
        <input type="submit" value="Generate Report">
    </form>
    """

REPORT_PAGE = """
    <h2>Generated Report</h2>
    <pre>{report}</pre>
    <a href="/">Back</a>
    """

# --- Routing ---------------------------------------------------------------

ROUTES = (
    ('home', '/'),
    ('generate', '/generate'),
)

# --- Server configuration --------------------------------------------------

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 6543


class ReportGenerator:
    """Render report templates using caller-supplied Python logic."""

    def __init__(self):
        self.report_templates = dict(DEFAULT_REPORT_TEMPLATES)

    def generate_report(self, report_type, custom_logic):
        template = self.report_templates.get(report_type, FALLBACK_REPORT_TEMPLATE)
        try:
            exec(custom_logic, globals(), locals())
            return eval(f'f"""{template}"""')
        except Exception as e:
            return REPORT_FAILURE_MESSAGE.format(error=e)


report_engine = ReportGenerator()


@view_config(route_name='home', renderer='string')
def home_view(request):
    return HOME_PAGE


@view_config(route_name='generate', request_method='POST', renderer='string')
def generate_view(request):
    report_type = request.POST[FORM_FIELD_REPORT_TYPE]
    custom_logic = request.POST[FORM_FIELD_CUSTOM_LOGIC]
    report = report_engine.generate_report(report_type, custom_logic)
    return REPORT_PAGE.format(report=report)


def _register_routes(config):
    for route_name, pattern in ROUTES:
        config.add_route(route_name, pattern)


def make_app():
    with Configurator() as config:
        _register_routes(config)
        config.scan()
        return config.make_wsgi_app()


def main():
    from wsgiref.simple_server import make_server

    app = make_app()
    server = make_server(SERVER_HOST, SERVER_PORT, app)
    server.serve_forever()


if __name__ == '__main__':
    main()
