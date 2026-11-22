from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
import os
import datetime
from enum import Enum
from string import Template

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

DEFAULT_PERIOD = 'Q2 2023'
DATE_FORMAT = '%Y-%m-%d'

SALES_TEMPLATE_TEXT = 'Sales report for $period'
INVENTORY_TEMPLATE_TEXT = 'Inventory status as of $date'

INVALID_REPORT_TYPE_MESSAGE = 'Invalid report type'
REPORT_FAILURE_PREFIX = 'Report generation failed: '

ROUTE_HOME = 'home'
ROUTE_GENERATE = 'generate'
PATH_HOME = '/'
PATH_GENERATE = '/generate'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 6543

HOME_PAGE_HTML = (
    '\n    <h1>Corporate Report Generator</h1>\n'
    '    <form action="/generate" method="post">\n'
    '        Report Type: \n'
    '        <select name="report_type">\n'
    '            <option value="sales">Sales</option>\n'
    '            <option value="inventory">Inventory</option>\n'
    '        </select><br>\n'
    '        Custom Period: <input type="text" name="period" placeholder="e.g., Q2 2023"><br>\n'
    '        Custom Date: <input type="date" name="date"><br>\n'
    '        <input type="submit" value="Generate Report">\n'
    '    </form>\n'
    '    '
)

REPORT_PAGE_HTML_TEMPLATE = (
    '\n        <h2>Generated Report</h2>\n'
    '        <pre>{report}</pre>\n'
    '        <a href="/">Back</a>\n'
    '        '
)


# --------------------------------------------------------------------------
# Domain
# --------------------------------------------------------------------------

class ReportType(str, Enum):
    SALES = 'sales'
    INVENTORY = 'inventory'


def _build_report_templates():
    return {
        ReportType.SALES: Template(SALES_TEMPLATE_TEXT),
        ReportType.INVENTORY: Template(INVENTORY_TEMPLATE_TEXT),
    }


def _build_safe_vars():
    return {
        'datetime': datetime,
        'period': DEFAULT_PERIOD,
        'date': datetime.datetime.now().strftime(DATE_FORMAT),
    }


class ReportGenerator:

    def __init__(self):
        self.report_templates = _build_report_templates()
        self.safe_vars = _build_safe_vars()

    def _build_context(self, period=None, date=None):
        """Return substitution variables with optional overrides applied."""
        context = self.safe_vars.copy()
        if period:
            context['period'] = period
        if date:
            context['date'] = date
        return context

    def generate_report(self, report_type: ReportType, period: str=None, date: str=None):
        template = self.report_templates.get(report_type)
        if not template:
            return INVALID_REPORT_TYPE_MESSAGE
        context = self._build_context(period, date)
        try:
            return template.safe_substitute(context)
        except Exception as e:
            return f'{REPORT_FAILURE_PREFIX}{str(e)}'


report_engine = ReportGenerator()


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------

def _render_report_page(report):
    # NOTE: output is intentionally not escaped to preserve existing behaviour.
    return REPORT_PAGE_HTML_TEMPLATE.format(report=report)


@view_config(route_name=ROUTE_HOME, renderer='string')
def home_view(request):
    return HOME_PAGE_HTML


@view_config(route_name=ROUTE_GENERATE, request_method='POST', renderer='string')
def generate_view(request):
    try:
        report_type = ReportType(request.POST['report_type'])
        period = request.POST.get('period')
        date = request.POST.get('date')
        report = report_engine.generate_report(report_type, period, date)
        return _render_report_page(report)
    except ValueError as e:
        return f'{INVALID_REPORT_TYPE_MESSAGE}: {str(e)}'


# --------------------------------------------------------------------------
# Application setup
# --------------------------------------------------------------------------

def make_app():
    with Configurator() as config:
        config.add_route(ROUTE_HOME, PATH_HOME)
        config.add_route(ROUTE_GENERATE, PATH_GENERATE)
        config.scan()
        return config.make_wsgi_app()


def _serve(host=SERVER_HOST, port=SERVER_PORT):
    from wsgiref.simple_server import make_server
    app = make_app()
    server = make_server(host, port, app)
    server.serve_forever()


if __name__ == '__main__':
    _serve()
