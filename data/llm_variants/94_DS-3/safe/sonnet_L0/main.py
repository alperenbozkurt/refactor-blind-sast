import tornado.ioloop
import tornado.web
import os
import json
import html


MAIN_PAGE_HTML = '\n        <form action="/render" method="post">\n            <h1>Template Editor</h1>\n            Template Name: <input type="text" name="name"><br>\n            Template Content: <br>\n            <textarea name="content" rows=10 cols=50></textarea><br>\n            <input type="submit" value="Render">\n        </form>\n        '

RENDER_PAGE_HTML = '\n        <h2>Rendered Template: {name}</h2>\n        <div style="border:1px solid #ccc; padding:10px;">\n            {rendered}\n        </div>\n        <a href="/">Back</a>\n        '

APP_CONFIG = {'debug': True, 'version': '1.0', 'features': ['template', 'render']}


def _render_content(content):
    try:
        return html.escape(content).replace('\n', '<br>')
    except Exception as e:
        return f'Error: {html.escape(str(e))}'


class MainHandler(tornado.web.RequestHandler):

    def get(self):
        self.write(MAIN_PAGE_HTML)


class TemplateHandler(tornado.web.RequestHandler):

    def post(self):
        template_name = self.get_body_argument('name')
        template_content = self.get_body_argument('content')
        rendered = _render_content(template_content)
        self.write(RENDER_PAGE_HTML.format(name=html.escape(template_name), rendered=rendered))


class ConfigHandler(tornado.web.RequestHandler):

    def get(self):
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(APP_CONFIG))


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
