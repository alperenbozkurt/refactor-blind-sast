import falcon
import json
import uuid
from datetime import datetime
from wsgiref import simple_server


class ReportStorage:

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


def _render_report_html(report):
    return f"""\n                    <!DOCTYPE html>\n                    <html>\n                    <head>\n                        <title>{report['title']}</title>\n                        <style>\n                            .report {{ max-width: 800px; margin: 0 auto; }}\n                            .report-header {{ border-bottom: 1px solid #eee; padding-bottom: 10px; }}\n                            .report-content {{ margin-top: 20px; }}\n                        </style>\n                    </head>\n                    <body>\n                        <div class="report">\n                            <div class="report-header">\n                                <h1>{report['title']}</h1>\n                                <p>By {report['author']} | Created at {report['created_at']}</p>\n                            </div>\n                            <div class="report-content">\n                                {report['content']}\n                            </div>\n                        </div>\n                    </body>\n                    </html>\n                    """


_REPORT_FORM_HTML = '\n        <!DOCTYPE html>\n        <html>\n        <head>\n            <title>Create New Report</title>\n        </head>\n        <body>\n            <h1>Create New Report</h1>\n            <form id="reportForm">\n                <label>Title: <input type="text" name="title" required></label><br>\n                <label>Content (HTML): <textarea name="content" required></textarea></label><br>\n                <label>Author: <input type="text" name="author"></label><br>\n                <button type="submit">Create Report</button>\n            </form>\n            <div id="result"></div>\n            <script>\n                document.getElementById(\'reportForm\').addEventListener(\'submit\', async (e) => {\n                    e.preventDefault();\n                    const formData = {\n                        title: e.target.title.value,\n                        content: e.target.content.value,\n                        author: e.target.author.value || \'Anonymous\'\n                    };\n                    \n                    const response = await fetch(\'/reports\', {\n                        method: \'POST\',\n                        headers: { \'Content-Type\': \'application/json\' },\n                        body: JSON.stringify(formData)\n                    });\n                    \n                    const result = await response.json();\n                    document.getElementById(\'result\').innerHTML = \n                        `Report created! <a href="/reports/${result.id}">View report</a>`;\n                });\n            </script>\n        </body>\n        </html>\n        '


class ReportResource:

    def on_get(self, req, resp, report_id=None):
        if not report_id:
            resp.media = report_storage.get_all_reports()
            return

        report = report_storage.get_report(report_id)
        if not report:
            resp.status = falcon.HTTP_404
            return

        resp.content_type = 'text/html'
        resp.text = _render_report_html(report)

    def on_post(self, req, resp):
        try:
            data = json.loads(req.stream.read().decode('utf-8'))
            report_id = report_storage.create_report(
                data['title'],
                data['content'],
                data.get('author', 'Anonymous'),
            )
            resp.media = {'id': report_id}
        except Exception as e:
            raise falcon.HTTPBadRequest('Invalid request', str(e))


class ReportFormResource:

    def on_get(self, req, resp):
        resp.content_type = 'text/html'
        resp.text = _REPORT_FORM_HTML


app = falcon.App()
app.add_route('/reports', ReportResource())
app.add_route('/reports/{report_id}', ReportResource())
app.add_route('/create-report', ReportFormResource())

if __name__ == '__main__':
    httpd = simple_server.make_server('0.0.0.0', 8000, app)
    httpd.serve_forever()
