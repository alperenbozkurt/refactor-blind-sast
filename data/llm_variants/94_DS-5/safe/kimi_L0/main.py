import datetime
import os
from enum import Enum
from string import Template

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config


class ReportType(str, Enum):
    SALES = 'sales'
    INVENTORY = 'inventory'


class ReportGenerator:
    """Builds text reports from a fixed set of string templates."""

    def __init__(self):
        self.report_templates = {
            ReportType.SALES: Template('Sales report for $period'),
            ReportType.INVENTORY: Template('Inventory status as of $date'),
        }
        self.safe_vars = {
            'datetime': datetime,
            'period': 'Q2 2023',
            'date': datetime.datetime.now().strftime('%Y-%m-%d'),
        }

    def generate_report(self, report_type: ReportType, period: str = None, date: str = None):
        template = self.report_templates.get(report_type)
        if template is None:
            return 'Invalid report type'

        variables = self.safe_vars.copy()
        if period:
            variables['period'] = period
        if date:
            variables['date'] = date

        try:
            return template.safe_substitute(variables)
        except Exception as exc:
            return f'Report generation failed: {exc}'


report_engine = ReportGenerator()


@view_config(route_name='home', renderer='string')
def home_view(request):
    return """
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


@view_config(route_name='generate', request_method='POST', renderer='string')
def generate_view(request):
    try:
        report_type = ReportType(request.POST['report_type'])
        period = request.POST.get('period')
        date = request.POST.get('date')
        report = report_engine.generate_report(report_type, period, date)
        return f"""
        <h2>Generated Report</h2>
        <pre>{report}</pre>
        <a href="/">Back</a>
        """
    except ValueError as exc:
        return f'Invalid report type: {exc}'


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
