import tornado.ioloop
import tornado.web
import os
import json

SERVER_PORT = 8888

EDITOR_FORM_HTML = """
        <form action="/render" method="post">
            <h1>Template Editor</h1>
            Template Name: <input type="text" name="name"><br>
            Template Content: <br>
            <textarea name="content" rows=10 cols=50></textarea><br>
            <input type="submit" value="Render">
        </form>
        """

APP_CONFIG = {
    'debug': True,
    'version': '1.0',
    'features': ['template', 'render'],
}


def render_template_content(content):
    """Evaluate the content as an f-string and return the result or the error text."""
    locals_dict = {}
    globals_dict = {'__builtins__': None}
    try:
        exec(f"result = f'''{content}'''", globals_dict, locals_dict)
        return locals_dict.get('result', '')
    except Exception as e:
        return str(e)


class MainHandler(tornado.web.RequestHandler):

    def get(self):
        self.write(EDITOR_FORM_HTML)


class TemplateHandler(tornado.web.RequestHandler):

    def post(self):
        template_name = self.get_body_argument('name')
        template_content = self.get_body_argument('content')

        rendered = render_template_content(template_content)

        self.write(f"""
        <h2>Rendered Template: {template_name}</h2>
        <div style="border:1px solid #ccc; padding:10px;">
            {rendered}
        </div>
        <a href="/">Back</a>
        """)


class ConfigHandler(tornado.web.RequestHandler):

    def get(self):
        config = dict(APP_CONFIG)
        config['features'] = list(APP_CONFIG['features'])
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
    app.listen(SERVER_PORT)
    tornado.ioloop.IOLoop.current().start()
