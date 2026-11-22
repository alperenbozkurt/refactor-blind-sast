from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
import os
import datetime
from enum import Enum
from string import Template

DEFAULT_PERIOD = 'Q2 2023'
DATE_FORMAT = '%Y-%m-%d'

HOME_PAGE_HTML = (
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

GENERATED_REPORT_HTML = (
    '\n'
    '        <h2>Generated Report</h2>\n'
    '        <pre>{report}</pre>\n'
    '        <a href="/">Back</a>\n'
    '        '
)


class ReportType(str, Enum):
    SALES = 'sales'
    INVENTORY = 'inventory'


class ReportGenerator:

    def __init__(self):
        self.report_templates = {
            ReportType.SALES: Template('Sales report for $period'),
            ReportType.INVENTORY: Template('Inventory status as of $date'),
        }
        self.safe_vars = {
            'datetime': datetime,
            'period': DEFAULT_PERIOD,
            'date': datetime.datetime.now().strftime(DATE_FORMAT),
        }

    def generate_report(self, report_type: ReportType, period: str = None, date: str = None):
        template = self.report_templates.get(report_type)
        if not template:
            return 'Invalid report type'

        substitutions = self._build_substitutions(period, date)
        try:
            return template.safe_substitute(substitutions)
        except Exception as e:
            return f'Report generation failed: {str(e)}'

    def _build_substitutions(self, period, date):
        """Return the default variables overridden by any provided values."""
        substitutions = self.safe_vars.copy()
        if period:
            substitutions['period'] = period
        if date:
            substitutions['date'] = date
        return substitutions


report_engine = ReportGenerator()


@view_config(route_name='home', renderer='string')
def home_view(request):
    return HOME_PAGE_HTML


@view_config(route_name='generate', request_method='POST', renderer='string')
def generate_view(request):
    try:
        report_type = ReportType(request.POST['report_type'])
        period = request.POST.get('period')
        date = request.POST.get('date')
        report = report_engine.generate_report(report_type, period, date)
        return GENERATED_REPORT_HTML.format(report=report)
    except ValueError as e:
        return f'Invalid report type: {str(e)}'


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
