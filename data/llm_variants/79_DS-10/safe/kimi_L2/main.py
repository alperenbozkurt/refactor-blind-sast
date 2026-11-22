"""Falcon-based web application for creating and viewing reports."""

import html
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from wsgiref import simple_server

import falcon

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_AUTHOR = 'Anonymous'
HTML_CONTENT_TYPE = 'text/html'

ROUTE_REPORTS = '/reports'
ROUTE_REPORT = '/reports/{report_id}'
ROUTE_CREATE_REPORT = '/create-report'

# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

REPORT_TEMPLATE = """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>{title}</title>
                        <style>
                            .report {{ max-width: 800px; margin: 0 auto; }}
                            .report-header {{ border-bottom: 1px solid #eee; padding-bottom: 10px; }}
                            .report-content {{ margin-top: 20px; }}
                        </style>
                    </head>
                    <body>
                        <div class="report">
                            <div class="report-header">
                                <h1>{title}</h1>
                                <p>By {author} | Created at {created_at}</p>
                            </div>
                            <div class="report-content">
                                {content}
                            </div>
                        </div>
                    </body>
                    </html>
                    """

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
# Rendering and request helpers
# ---------------------------------------------------------------------------

def render_report_html(report):
    """Render a stored report as a standalone, fully escaped HTML page."""
    return REPORT_TEMPLATE.format(
        title=html.escape(report['title']),
        author=html.escape(report['author']),
        created_at=html.escape(report['created_at']),
        content=html.escape(report['content']),
    )


def parse_json_body(req):
    """Read and decode the JSON body of a request."""
    return json.loads(req.stream.read().decode('utf-8'))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServerConfig:
    """Network settings for the bundled WSGI development server."""

    host: str = '0.0.0.0'
    port: int = 8000


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

class ReportStorage:
    """In-memory storage for reports."""

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
    """Endpoint for listing, creating and displaying reports."""

    def on_get(self, req, resp, report_id=None):
        if report_id:
            self._respond_with_report(resp, report_id)
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

    def _respond_with_report(self, resp, report_id):
        report = report_storage.get_report(report_id)
        if not report:
            resp.status = falcon.HTTP_404
            return
        resp.content_type = HTML_CONTENT_TYPE
        resp.text = render_report_html(report)


class ReportFormResource:
    """Serves the HTML form used to create new reports."""

    def on_get(self, req, resp):
        resp.content_type = HTML_CONTENT_TYPE
        resp.text = REPORT_FORM_HTML


# ---------------------------------------------------------------------------
# Application assembly
# ---------------------------------------------------------------------------

def create_app():
    """Build the Falcon application and register all routes."""
    application = falcon.App()
    report_resource = ReportResource()
    application.add_route(ROUTE_REPORTS, report_resource)
    application.add_route(ROUTE_REPORT, report_resource)
    application.add_route(ROUTE_CREATE_REPORT, ReportFormResource())
    return application


app = create_app()


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main():
    """Start the development WSGI server."""
    config = ServerConfig()
    httpd = simple_server.make_server(config.host, config.port, app)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
