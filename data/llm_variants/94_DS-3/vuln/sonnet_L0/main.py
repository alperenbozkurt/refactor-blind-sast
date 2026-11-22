import tornado.ioloop
import tornado.web
import os  # noqa: F401  (kept to preserve module-level names)
import json

MAIN_PAGE_HTML = (
    '\n'
    '        <form action="/render" method="post">\n'
    '            <h1>Template Editor</h1>\n'
    '            Template Name: <input type="text" name="name"><br>\n'
    '            Template Content: <br>\n'
    '            <textarea name="content" rows=10 cols=50></textarea><br>\n'
    '            <input type="submit" value="Render">\n'
    '        </form>\n'
    '        '
)

RENDERED_PAGE_HTML = (
    '\n'
    '        <h2>Rendered Template: {name}</h2>\n'
    '        <div style="border:1px solid #ccc; padding:10px;">\n'
    '            {rendered}\n'
    '        </div>\n'
    '        <a href="/">Back</a>\n'
    '        '
)

CONFIG = {
    'debug': True,
    'version': '1.0',
    'features': ['template', 'render'],
}


def _render_content(content):
    locals_dict = {}
    globals_dict = {'__builtins__': None}
    try:
        exec(f"result = f'''{content}'''", globals_dict, locals_dict)
        return locals_dict.get('result', '')
    except Exception as e:
        return str(e)


class MainHandler(tornado.web.RequestHandler):

    def get(self):
        self.write(MAIN_PAGE_HTML)


class TemplateHandler(tornado.web.RequestHandler):

    def post(self):
        template_name = self.get_body_argument('name')
        template_content = self.get_body_argument('content')
        rendered = _render_content(template_content)
        self.write(RENDERED_PAGE_HTML.format(name=template_name, rendered=rendered))


class ConfigHandler(tornado.web.RequestHandler):

    def get(self):
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(CONFIG))


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
