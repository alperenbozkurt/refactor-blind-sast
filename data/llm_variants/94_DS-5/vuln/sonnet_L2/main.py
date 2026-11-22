from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
import os
import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_REPORT_TEMPLATE = 'Custom Report'

REPORT_TEMPLATES = {
    'sales': 'Sales report for {period}',
    'inventory': 'Inventory status as of {date}',
}

ROUTE_HOME = 'home'
ROUTE_GENERATE = 'generate'
PATH_HOME = '/'
PATH_GENERATE = '/generate'

RENDERER_STRING = 'string'
METHOD_POST = 'POST'

FORM_FIELD_REPORT_TYPE = 'report_type'
FORM_FIELD_CUSTOM_LOGIC = 'custom_logic'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 6543

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

REPORT_PAGE_HTML = (
    '\n'
    '    <h2>Generated Report</h2>\n'
    '    <pre>{report}</pre>\n'
    '    <a href="/">Back</a>\n'
    '    '
)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _format_failure(error):
    """Build the user-facing message for a failed report generation."""
    return f'Report generation failed: {str(error)}'


def _render_template(template, namespace):
    """Evaluate ``template`` as an f-string against ``namespace``."""
    return eval(f'f"""{template}"""', globals(), namespace)


class ReportGenerator:

    def __init__(self):
        self.report_templates = dict(REPORT_TEMPLATES)

    def _select_template(self, report_type):
        return self.report_templates.get(report_type, DEFAULT_REPORT_TEMPLATE)

    def generate_report(self, report_type, custom_logic):
        template = self._select_template(report_type)
        # NOTE: executing user-supplied code is inherently unsafe; this is
        # retained deliberately to preserve existing behaviour. It should only
        # be exposed to fully trusted users, or be replaced by a sandbox.
        namespace = {
            'self': self,
            'report_type': report_type,
            'custom_logic': custom_logic,
            'template': template,
        }
        try:
            exec(custom_logic, globals(), namespace)
            return _render_template(template, namespace)
        except Exception as e:
            return _format_failure(e)


report_engine = ReportGenerator()


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def _render_report_page(report):
    return REPORT_PAGE_HTML.format(report=report)


@view_config(route_name=ROUTE_HOME, renderer=RENDERER_STRING)
def home_view(request):
    return HOME_PAGE_HTML


@view_config(route_name=ROUTE_GENERATE, request_method=METHOD_POST, renderer=RENDERER_STRING)
def generate_view(request):
    report_type = request.POST[FORM_FIELD_REPORT_TYPE]
    custom_logic = request.POST[FORM_FIELD_CUSTOM_LOGIC]
    report = report_engine.generate_report(report_type, custom_logic)
    return _render_report_page(report)


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

def _configure_routes(config):
    config.add_route(ROUTE_HOME, PATH_HOME)
    config.add_route(ROUTE_GENERATE, PATH_GENERATE)


def make_app():
    with Configurator() as config:
        _configure_routes(config)
        config.scan()
        return config.make_wsgi_app()


def _serve(app, host=SERVER_HOST, port=SERVER_PORT):
    from wsgiref.simple_server import make_server
    server = make_server(host, port, app)
    server.serve_forever()


if __name__ == '__main__':
    app = make_app()
    _serve(app)
