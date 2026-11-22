import html
import json
import uuid
from datetime import datetime
from wsgiref import simple_server

import falcon


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


class ReportResource:

    def on_get(self, req, resp, report_id=None):
        if not report_id:
            resp.media = report_storage.get_all_reports()
            return

        def render_report_html(report):
            escaped_title = html.escape(report['title'])
            escaped_author = html.escape(report['author'])
            escaped_created_at = html.escape(report['created_at'])
            escaped_content = html.escape(report['content'])
            return (
                f'\n                    <!DOCTYPE html>\n'
                f'                    <html>\n'
                f'                    <head>\n'
                f'                        <title>{escaped_title}</title>\n'
                f'                        <style>\n'
                f'                            .report {{ max-width: 800px; margin: 0 auto; }}\n'
                f'                            .report-header {{ border-bottom: 1px solid #eee; padding-bottom: 10px; }}\n'
                f'                            .report-content {{ margin-top: 20px; }}\n'
                f'                        </style>\n'
                f'                    </head>\n'
                f'                    <body>\n'
                f'                        <div class="report">\n'
                f'                            <div class="report-header">\n'
                f'                                <h1>{escaped_title}</h1>\n'
                f'                                <p>By {escaped_author} | Created at {escaped_created_at}</p>\n'
                f'                            </div>\n'
                f'                            <div class="report-content">\n'
                f'                                {escaped_content}\n'
                f'                            </div>\n'
                f'                        </div>\n'
                f'                    </body>\n'
                f'                    </html>\n'
                f'                    '
            )

        report = report_storage.get_report(report_id)
        if report:
            resp.content_type = 'text/html'
            resp.text = render_report_html(report)
        else:
            resp.status = falcon.HTTP_404

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
        resp.text = (
            '\n        <!DOCTYPE html>\n'
            '        <html>\n'
            '        <head>\n'
            '            <title>Create New Report</title>\n'
            '        </head>\n'
            '        <body>\n'
            '            <h1>Create New Report</h1>\n'
            '            <form id="reportForm">\n'
            '                <label>Title: <input type="text" name="title" required></label><br>\n'
            '                <label>Content (HTML): <textarea name="content" required></textarea></label><br>\n'
            '                <label>Author: <input type="text" name="author"></label><br>\n'
            '                <button type="submit">Create Report</button>\n'
            '            </form>\n'
            '            <div id="result"></div>\n'
            '            <script>\n'
            "                document.getElementById('reportForm').addEventListener('submit', async (e) => {\n"
            '                    e.preventDefault();\n'
            '                    const formData = {\n'
            '                        title: e.target.title.value,\n'
            '                        content: e.target.content.value,\n'
            "                        author: e.target.author.value || 'Anonymous'\n"
            '                    };\n'
            '                    \n'
            "                    const response = await fetch('/reports', {\n"
            "                        method: 'POST',\n"
            "                        headers: { 'Content-Type': 'application/json' },\n"
            '                        body: JSON.stringify(formData)\n'
            '                    });\n'
            '                    \n'
            '                    const result = await response.json();\n'
            "                    document.getElementById('result').innerHTML = \n"
            '                        `Report created! <a href="/reports/${result.id}">View report</a>`;\n'
            '                });\n'
            '            </script>\n'
            '        </body>\n'
            '        </html>\n'
            '        '
        )


app = falcon.App()
app.add_route('/reports', ReportResource())
app.add_route('/reports/{report_id}', ReportResource())
app.add_route('/create-report', ReportFormResource())


if __name__ == '__main__':
    httpd = simple_server.make_server('0.0.0.0', 8000, app)
    httpd.serve_forever()
