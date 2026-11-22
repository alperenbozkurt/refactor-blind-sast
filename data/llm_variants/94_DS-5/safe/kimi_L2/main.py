"""Corporate report generator web application.

A small Pyramid service that renders sales and inventory reports from
string templates with safe variable substitution.
"""

import datetime
import os  # noqa: F401  (retained as part of the module's public surface)
from dataclasses import dataclass
from enum import Enum
from string import Template

from pyramid.config import Configurator
from pyramid.response import Response  # noqa: F401  (retained for compatibility)
from pyramid.view import view_config

# --- Report template configuration -----------------------------------------

SALES_REPORT_TEMPLATE = 'Sales report for $period'
INVENTORY_REPORT_TEMPLATE = 'Inventory status as of $date'

DEFAULT_PERIOD = 'Q2 2023'
DATE_FORMAT = '%Y-%m-%d'

INVALID_REPORT_TYPE_MESSAGE = 'Invalid report type'
REPORT_FAILURE_MESSAGE = 'Report generation failed: {error}'

# --- Page markup -----------------------------------------------------------

HOME_PAGE = (
    '\n'
    '    <h1>Corporate Report Generator</h1>\n'
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

# --- Routing configuration --------------------------------------------------

HOME_ROUTE_NAME = 'home'
GENERATE_ROUTE_NAME = 'generate'
HOME_ROUTE_PATH = '/'
GENERATE_ROUTE_PATH = '/generate'


@dataclass(frozen=True)
class ServerConfig:
    """Network settings for the built-in WSGI server."""

    host: str = '0.0.0.0'
    port: int = 6543


class ReportType(str, Enum):
    SALES = 'sales'
    INVENTORY = 'inventory'


class ReportGenerator:
    """Builds reports by safely substituting variables into templates."""

    def __init__(self):
        self.report_templates = self._build_report_templates()
        self.safe_vars = self._build_safe_vars()

    @staticmethod
    def _build_report_templates():
        return {
            ReportType.SALES: Template(SALES_REPORT_TEMPLATE),
            ReportType.INVENTORY: Template(INVENTORY_REPORT_TEMPLATE),
        }

    @staticmethod
    def _build_safe_vars():
        return {
            'datetime': datetime,
            'period': DEFAULT_PERIOD,
            'date': datetime.datetime.now().strftime(DATE_FORMAT),
        }

    def _substitution_variables(self, period, date):
        variables = self.safe_vars.copy()
        if period:
            variables['period'] = period
        if date:
            variables['date'] = date
        return variables

    def generate_report(self, report_type: ReportType, period: str=None, date: str=None):
        template = self.report_templates.get(report_type)
        if not template:
            return INVALID_REPORT_TYPE_MESSAGE
        variables = self._substitution_variables(period, date)
        try:
            return template.safe_substitute(variables)
        except Exception as e:
            return REPORT_FAILURE_MESSAGE.format(error=str(e))


report_engine = ReportGenerator()


def _render_report_page(report):
    return f"""
        <h2>Generated Report</h2>
        <pre>{report}</pre>
        <a href="/">Back</a>
        """


def _parse_report_request(request):
    report_type = ReportType(request.POST['report_type'])
    period = request.POST.get('period')
    date = request.POST.get('date')
    return report_type, period, date


@view_config(route_name=HOME_ROUTE_NAME, renderer='string')
def home_view(request):
    return HOME_PAGE


@view_config(route_name=GENERATE_ROUTE_NAME, request_method='POST', renderer='string')
def generate_view(request):
    try:
        report_type, period, date = _parse_report_request(request)
        report = report_engine.generate_report(report_type, period, date)
        return _render_report_page(report)
    except ValueError as e:
        return f'Invalid report type: {str(e)}'


def make_app():
    with Configurator() as config:
        config.add_route(HOME_ROUTE_NAME, HOME_ROUTE_PATH)
        config.add_route(GENERATE_ROUTE_NAME, GENERATE_ROUTE_PATH)
        config.scan()
        return config.make_wsgi_app()


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    app = make_app()
    server_config = ServerConfig()
    server = make_server(server_config.host, server_config.port, app)
    server.serve_forever()
