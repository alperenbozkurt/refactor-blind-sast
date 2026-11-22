"""Corporate report generator web application.

Provides a small Pyramid app that renders HTML reports for a fixed set of
report types. Run this module directly to serve the app on 0.0.0.0:6543.
"""

import datetime
import os
from enum import Enum
from string import Template

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config

SALES_REPORT_TEMPLATE = 'Sales report for $period'
INVENTORY_REPORT_TEMPLATE = 'Inventory status as of $date'

DEFAULT_PERIOD = 'Q2 2023'
DATE_FORMAT = '%Y-%m-%d'

HOME_PAGE = """
    <h1>Corporate Report Generator</h1>
    <form action="/generate" method="post">
        Report Type: 
        <select name="report_type">
            <option value="sales">Sales</option>
            <option value="inventory">Inventory</option>
        </select><br>
        Custom Period: <input type="text" name="period" placeholder="e.g., Q2 2023"><br>
        Custom Date: <input type="date" name="date"><br>
        <input type="submit" value="Generate Report">
    </form>
    """

REPORT_PAGE = """
        <h2>Generated Report</h2>
        <pre>{report}</pre>
        <a href="/">Back</a>
        """

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 6543


class ReportType(str, Enum):
    """Supported kinds of reports."""

    SALES = 'sales'
    INVENTORY = 'inventory'


class ReportGenerator:
    """Builds report strings from predefined templates."""

    def __init__(self):
        self.report_templates = {
            ReportType.SALES: Template(SALES_REPORT_TEMPLATE),
            ReportType.INVENTORY: Template(INVENTORY_REPORT_TEMPLATE),
        }
        self.safe_vars = {
            'datetime': datetime,
            'period': DEFAULT_PERIOD,
            'date': datetime.datetime.now().strftime(DATE_FORMAT),
        }

    def generate_report(self, report_type: ReportType, period: str=None, date: str=None):
        """Render the requested report, or an error message on failure."""
        template = self.report_templates.get(report_type)
        if not template:
            return 'Invalid report type'
        template_vars = self.safe_vars.copy()
        if period:
            template_vars['period'] = period
        if date:
            template_vars['date'] = date
        try:
            return template.safe_substitute(template_vars)
        except Exception as e:
            return f'Report generation failed: {str(e)}'


report_engine = ReportGenerator()


@view_config(route_name='home', renderer='string')
def home_view(request):
    """Render the report selection form."""
    return HOME_PAGE


@view_config(route_name='generate', request_method='POST', renderer='string')
def generate_view(request):
    """Render the requested report, or an error for unknown report types."""
    try:
        report_type = ReportType(request.POST['report_type'])
        period = request.POST.get('period')
        date = request.POST.get('date')
        report = report_engine.generate_report(report_type, period, date)
        return REPORT_PAGE.format(report=report)
    except ValueError as e:
        return f'Invalid report type: {str(e)}'


def make_app():
    """Create and configure the WSGI application."""
    with Configurator() as config:
        config.add_route('home', '/')
        config.add_route('generate', '/generate')
        config.scan()
        return config.make_wsgi_app()


if __name__ == '__main__':
    from wsgiref.simple_server import make_server

    app = make_app()
    server = make_server(SERVER_HOST, SERVER_PORT, app)
    server.serve_forever()
