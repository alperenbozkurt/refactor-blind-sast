import json
import os

import tornado.ioloop
import tornado.web


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(
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


class TemplateHandler(tornado.web.RequestHandler):
    def post(self):
        template_name = self.get_body_argument('name')
        template_content = self.get_body_argument('content')

        def render(content):
            locals_dict = {}
            globals_dict = {'__builtins__': None}
            try:
                exec(f"result = f'''{content}'''", globals_dict, locals_dict)
                return locals_dict.get('result', '')
            except Exception as e:
                return str(e)

        rendered = render(template_content)
        self.write(
            '\n'
            f'        <h2>Rendered Template: {template_name}</h2>\n'
            '        <div style="border:1px solid #ccc; padding:10px;">\n'
            f'            {rendered}\n'
            '        </div>\n'
            '        <a href="/">Back</a>\n'
            '        '
        )


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
