"""Minimal Tornado application for editing and rendering templates."""

import html
import json
import os

import tornado.ioloop
import tornado.web

PORT = 8888

CONFIG = {
    'debug': True,
    'version': '1.0',
    'features': ['template', 'render'],
}

FORM_PAGE = '''
        <form action="/render" method="post">
            <h1>Template Editor</h1>
            Template Name: <input type="text" name="name"><br>
            Template Content: <br>
            <textarea name="content" rows=10 cols=50></textarea><br>
            <input type="submit" value="Render">
        </form>
        '''

RENDERED_PAGE = '''
        <h2>Rendered Template: {name}</h2>
        <div style="border:1px solid #ccc; padding:10px;">
            {rendered}
        </div>
        <a href="/">Back</a>
        '''


def render_content(content):
    """Escape *content* for HTML and convert newlines to <br> tags."""
    try:
        return html.escape(content).replace('\n', '<br>')
    except Exception as e:
        return f'Error: {html.escape(str(e))}'


class MainHandler(tornado.web.RequestHandler):
    """Serve the template editor form."""

    def get(self):
        self.write(FORM_PAGE)


class TemplateHandler(tornado.web.RequestHandler):
    """Render submitted template content."""

    def post(self):
        template_name = self.get_body_argument('name')
        template_content = self.get_body_argument('content')
        rendered = render_content(template_content)
        self.write(RENDERED_PAGE.format(
            name=html.escape(template_name),
            rendered=rendered,
        ))


class ConfigHandler(tornado.web.RequestHandler):
    """Return the application configuration as JSON."""

    def get(self):
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(CONFIG))


ROUTES = [
    ('/', MainHandler),
    ('/render', TemplateHandler),
    ('/config', ConfigHandler),
]


def make_app():
    return tornado.web.Application(ROUTES)


def main():
    app = make_app()
    app.listen(PORT)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
