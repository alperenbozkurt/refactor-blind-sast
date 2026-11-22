import falcon
import json
import uuid
from datetime import datetime
from wsgiref import simple_server

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

HTML_CONTENT_TYPE = 'text/html'
DEFAULT_AUTHOR = 'Anonymous'
REQUEST_ENCODING = 'utf-8'

REPORTS_ROUTE = '/reports'
REPORT_ITEM_ROUTE = '/reports/{report_id}'
CREATE_REPORT_ROUTE = '/create-report'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

_REPORT_TEMPLATE_BASE_INDENT = ' ' * 20
_FORM_TEMPLATE_BASE_INDENT = ' ' * 8


def _build_html_document(lines, base_indent):
    """Assemble an HTML document from relatively indented lines.

    The result starts with a newline, every line is prefixed with
    ``base_indent`` and terminated by a newline, and the document ends with
    a trailing ``base_indent``.
    """
    body = ''.join(base_indent + line + '\n' for line in lines)
    return '\n' + body + base_indent


# --------------------------------------------------------------------------- #
# HTML templates
# --------------------------------------------------------------------------- #

_REPORT_TEMPLATE_LINES = (
    '<!DOCTYPE html>',
    '<html>',
    '<head>',
    '    <title>{title}</title>',
    '    <style>',
    '        .report {{ max-width: 800px; margin: 0 auto; }}',
    '        .report-header {{ border-bottom: 1px solid #eee; padding-bottom: 10px; }}',
    '        .report-content {{ margin-top: 20px; }}',
    '    </style>',
    '</head>',
    '<body>',
    '    <div class="report">',
    '        <div class="report-header">',
    '            <h1>{title}</h1>',
    '            <p>By {author} | Created at {created_at}</p>',
    '        </div>',
    '        <div class="report-content">',
    '            {content}',
    '        </div>',
    '    </div>',
    '</body>',
    '</html>',
)

REPORT_TEMPLATE = _build_html_document(
    _REPORT_TEMPLATE_LINES, _REPORT_TEMPLATE_BASE_INDENT
)

_FORM_TEMPLATE_LINES = (
    '<!DOCTYPE html>',
    '<html>',
    '<head>',
    '    <title>Create New Report</title>',
    '</head>',
    '<body>',
    '    <h1>Create New Report</h1>',
    '    <form id="reportForm">',
    '        <label>Title: <input type="text" name="title" required></label><br>',
    '        <label>Content (HTML): <textarea name="content" required></textarea></label><br>',
    '        <label>Author: <input type="text" name="author"></label><br>',
    '        <button type="submit">Create Report</button>',
    '    </form>',
    '    <div id="result"></div>',
    '    <script>',
    "        document.getElementById('reportForm').addEventListener('submit', async (e) => {",
    '            e.preventDefault();',
    '            const formData = {',
    '                title: e.target.title.value,',
    '                content: e.target.content.value,',
    "                author: e.target.author.value || 'Anonymous'",
    '            };',
    '            ',
    "            const response = await fetch('/reports', {",
    "                method: 'POST',",
    "                headers: { 'Content-Type': 'application/json' },",
    '                body: JSON.stringify(formData)',
    '            });',
    '            ',
    '            const result = await response.json();',
    "            document.getElementById('result').innerHTML = ",
    '                `Report created! <a href="/reports/${result.id}">View report</a>`;',
    '        });',
    '    </script>',
    '</body>',
    '</html>',
)

REPORT_FORM_HTML = _build_html_document(
    _FORM_TEMPLATE_LINES, _FORM_TEMPLATE_BASE_INDENT
)


def render_report_html(report):
    """Render a single report dictionary as an HTML page."""
    return REPORT_TEMPLATE.format(
        title=report['title'],
        author=report['author'],
        created_at=report['created_at'],
        content=report['content'],
    )


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #

class ReportStorage:

    def __init__(self):
        self.reports = {}

    @staticmethod
    def _generate_id():
        return str(uuid.uuid4())

    @staticmethod
    def _timestamp():
        return datetime.now().isoformat()

    def create_report(self, title, content, author):
        report_id = self._generate_id()
        self.reports[report_id] = {
            'id': report_id,
            'title': title,
            'content': content,
            'author': author,
            'created_at': self._timestamp(),
        }
        return report_id

    def get_report(self, report_id):
        return self.reports.get(report_id)

    def get_all_reports(self):
        return list(self.reports.values())


report_storage = ReportStorage()


# --------------------------------------------------------------------------- #
# Resources
# --------------------------------------------------------------------------- #

def _parse_json_body(req):
    return json.loads(req.stream.read().decode(REQUEST_ENCODING))


def _respond_html(resp, html):
    resp.content_type = HTML_CONTENT_TYPE
    resp.text = html


class ReportResource:

    def on_get(self, req, resp, report_id=None):
        if report_id:
            self._get_single_report(resp, report_id)
        else:
            resp.media = report_storage.get_all_reports()

    def on_post(self, req, resp):
        try:
            data = _parse_json_body(req)
            report_id = report_storage.create_report(
                data['title'],
                data['content'],
                data.get('author', DEFAULT_AUTHOR),
            )
            resp.media = {'id': report_id}
        except Exception as e:
            raise falcon.HTTPBadRequest('Invalid request', str(e))

    @staticmethod
    def _get_single_report(resp, report_id):
        report = report_storage.get_report(report_id)
        if report:
            _respond_html(resp, render_report_html(report))
        else:
            resp.status = falcon.HTTP_404


class ReportFormResource:

    def on_get(self, req, resp):
        _respond_html(resp, REPORT_FORM_HTML)


# --------------------------------------------------------------------------- #
# Application wiring
# --------------------------------------------------------------------------- #

def _configure_routes(application):
    application.add_route(REPORTS_ROUTE, ReportResource())
    application.add_route(REPORT_ITEM_ROUTE, ReportResource())
    application.add_route(CREATE_REPORT_ROUTE, ReportFormResource())


app = falcon.App()
_configure_routes(app)


def main():
    httpd = simple_server.make_server(SERVER_HOST, SERVER_PORT, app)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
