"""Report publishing web service built on Falcon.

Exposes a small JSON/HTML API for creating, listing and viewing reports,
plus a browser form for creating new reports. Run the module directly to
serve the application with the built-in WSGI server.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from string import Template
from wsgiref import simple_server

import falcon

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_AUTHOR = 'Anonymous'
HTML_CONTENT_TYPE = 'text/html'

REPORTS_ROUTE = '/reports'
REPORT_DETAIL_ROUTE = '/reports/{report_id}'
CREATE_REPORT_ROUTE = '/create-report'


@dataclass(frozen=True)
class ServerConfig:
    """Network settings for the built-in development WSGI server."""

    host: str = '0.0.0.0'
    port: int = 8000


SERVER_CONFIG = ServerConfig()

# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------
# NOTE: The whitespace inside these templates is significant -- it is sent
# to clients verbatim as part of the response body and must be preserved.

REPORT_PAGE_TEMPLATE = Template("""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>$title</title>
                        <style>
                            .report { max-width: 800px; margin: 0 auto; }
                            .report-header { border-bottom: 1px solid #eee; padding-bottom: 10px; }
                            .report-content { margin-top: 20px; }
                        </style>
                    </head>
                    <body>
                        <div class="report">
                            <div class="report-header">
                                <h1>$title</h1>
                                <p>By $author | Created at $created_at</p>
                            </div>
                            <div class="report-content">
                                $content
                            </div>
                        </div>
                    </body>
                    </html>
                    """)

REPORT_FORM_HTML = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Create New Report</title>
        </head>
        <body>
            <h1>Create New Report</h1>
            <form id="reportForm">
                <label>Title: <input type="text" name="title" required></label><br>
                <label>Content (HTML): <textarea name="content" required></textarea></label><br>
                <label>Author: <input type="text" name="author"></label><br>
                <button type="submit">Create Report</button>
            </form>
            <div id="result"></div>
            <script>
                document.getElementById('reportForm').addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const formData = {
                        title: e.target.title.value,
                        content: e.target.content.value,
                        author: e.target.author.value || 'Anonymous'
                    };
                    
                    const response = await fetch('/reports', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(formData)
                    });
                    
                    const result = await response.json();
                    document.getElementById('result').innerHTML = 
                        `Report created! <a href="/reports/${result.id}">View report</a>`;
                });
            </script>
        </body>
        </html>
        """


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def render_report_html(report):
    """Render a single stored report as a standalone HTML page."""
    return REPORT_PAGE_TEMPLATE.substitute(
        title=report['title'],
        author=report['author'],
        created_at=report['created_at'],
        content=report['content'],
    )


def parse_json_body(req):
    """Read the request stream and decode it as UTF-8 JSON."""
    return json.loads(req.stream.read().decode('utf-8'))


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

class ReportStorage:
    """Simple in-memory storage for reports."""

    def __init__(self):
        self.reports = {}

    def create_report(self, title, content, author):
        report_id = str(uuid.uuid4())
        self.reports[report_id] = {
            'id': report_id,
            'title': title,
            'content': content,
            'author': author,
            'created_at': datetime.now().isoformat(),
        }
        return report_id

    def get_report(self, report_id):
        return self.reports.get(report_id)

    def get_all_reports(self):
        return list(self.reports.values())


report_storage = ReportStorage()


# ---------------------------------------------------------------------------
# HTTP resources
# ---------------------------------------------------------------------------

class ReportResource:
    """JSON/HTML endpoint for listing, creating and viewing reports."""

    def on_get(self, req, resp, report_id=None):
        if report_id:
            self._serve_report_page(resp, report_id)
        else:
            resp.media = report_storage.get_all_reports()

    def on_post(self, req, resp):
        try:
            data = parse_json_body(req)
            report_id = report_storage.create_report(
                data['title'],
                data['content'],
                data.get('author', DEFAULT_AUTHOR),
            )
            resp.media = {'id': report_id}
        except Exception as e:
            raise falcon.HTTPBadRequest('Invalid request', str(e))

    @staticmethod
    def _serve_report_page(resp, report_id):
        report = report_storage.get_report(report_id)
        if report:
            resp.content_type = HTML_CONTENT_TYPE
            resp.text = render_report_html(report)
        else:
            resp.status = falcon.HTTP_404


class ReportFormResource:
    """Serves the browser form used to create a new report."""

    def on_get(self, req, resp):
        resp.content_type = HTML_CONTENT_TYPE
        resp.text = REPORT_FORM_HTML


# ---------------------------------------------------------------------------
# Application assembly
# ---------------------------------------------------------------------------

def create_app():
    """Create the Falcon application and register all routes."""
    app = falcon.App()
    report_resource = ReportResource()
    app.add_route(REPORTS_ROUTE, report_resource)
    app.add_route(REPORT_DETAIL_ROUTE, report_resource)
    app.add_route(CREATE_REPORT_ROUTE, ReportFormResource())
    return app


app = create_app()


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def main():
    """Serve the application with the built-in WSGI server."""
    httpd = simple_server.make_server(SERVER_CONFIG.host, SERVER_CONFIG.port, app)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
