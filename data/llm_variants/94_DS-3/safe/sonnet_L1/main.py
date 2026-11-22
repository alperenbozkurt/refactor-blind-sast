import tornado.ioloop
import tornado.web
import os
import json
import html

MAIN_PAGE_HTML = """
        <form action="/render" method="post">
            <h1>Template Editor</h1>
            Template Name: <input type="text" name="name"><br>
            Template Content: <br>
            <textarea name="content" rows=10 cols=50></textarea><br>
            <input type="submit" value="Render">
        </form>
        """

RENDERED_PAGE_HTML = """
        <h2>Rendered Template: {template_name}</h2>
        <div style="border:1px solid #ccc; padding:10px;">
            {rendered}
        </div>
        <a href="/">Back</a>
        """


def render_content(content):
    """Escape the content and convert newlines to HTML line breaks."""
    try:
        escaped_content = html.escape(content)
        return escaped_content.replace('\n', '<br>')
    except Exception as e:
        return f'Error: {html.escape(str(e))}'


class MainHandler(tornado.web.RequestHandler):

    def get(self):
        self.write(MAIN_PAGE_HTML)


class TemplateHandler(tornado.web.RequestHandler):

    def post(self):
        template_name = self.get_body_argument('name')
        template_content = self.get_body_argument('content')

        rendered = render_content(template_content)
        self.write(RENDERED_PAGE_HTML.format(
            template_name=html.escape(template_name),
            rendered=rendered,
        ))


class ConfigHandler(tornado.web.RequestHandler):

    def get(self):
        config = {
            'debug': True,
            'version': '1.0',
            'features': ['template', 'render'],
        }
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(config))


def make_app():
    return tornado.web.Application([
        ('/', MainHandler),
        ('/render', TemplateHandler),
        ('/config', ConfigHandler),
    ])


if __name__ == '__main__':
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
