import tornado.ioloop
import tornado.web
import os
import json

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

SERVER_PORT = 8888

ROUTE_INDEX = '/'
ROUTE_RENDER = '/render'
ROUTE_CONFIG = '/config'

FORM_FIELD_NAME = 'name'
FORM_FIELD_CONTENT = 'content'

JSON_CONTENT_TYPE = 'application/json'

INDEX_PAGE_HTML = (
    '\n        <form action="/render" method="post">\n'
    '            <h1>Template Editor</h1>\n'
    '            Template Name: <input type="text" name="name"><br>\n'
    '            Template Content: <br>\n'
    '            <textarea name="content" rows=10 cols=50></textarea><br>\n'
    '            <input type="submit" value="Render">\n'
    '        </form>\n        '
)

RENDERED_PAGE_HTML_TEMPLATE = (
    '\n        <h2>Rendered Template: {template_name}</h2>\n'
    '        <div style="border:1px solid #ccc; padding:10px;">\n'
    '            {rendered}\n'
    '        </div>\n'
    '        <a href="/">Back</a>\n        '
)

APP_CONFIG = {
    'debug': True,
    'version': '1.0',
    'features': ['template', 'render'],
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def render_template_content(content):
    """Evaluate ``content`` as an f-string and return the result.

    On any error, the error message is returned as a string instead.
    """
    locals_dict = {}
    globals_dict = {'__builtins__': None}
    try:
        exec(f"result = f'''{content}'''", globals_dict, locals_dict)
        return locals_dict.get('result', '')
    except Exception as e:
        return str(e)


def build_rendered_page(template_name, rendered):
    """Build the HTML page showing a rendered template."""
    return RENDERED_PAGE_HTML_TEMPLATE.format(
        template_name=template_name, rendered=rendered
    )


def get_config_json():
    """Return the application configuration serialized as JSON."""
    return json.dumps(APP_CONFIG)


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #

class MainHandler(tornado.web.RequestHandler):

    def get(self):
        self.write(INDEX_PAGE_HTML)


class TemplateHandler(tornado.web.RequestHandler):

    def post(self):
        template_name = self.get_body_argument(FORM_FIELD_NAME)
        template_content = self.get_body_argument(FORM_FIELD_CONTENT)
        rendered = render_template_content(template_content)
        self.write(build_rendered_page(template_name, rendered))


class ConfigHandler(tornado.web.RequestHandler):

    def get(self):
        self.set_header('Content-Type', JSON_CONTENT_TYPE)
        self.write(get_config_json())


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #

def get_routes():
    """Return the list of (route, handler) pairs for the application."""
    return [
        (ROUTE_INDEX, MainHandler),
        (ROUTE_RENDER, TemplateHandler),
        (ROUTE_CONFIG, ConfigHandler),
    ]


def make_app():
    return tornado.web.Application(get_routes())


def main():
    app = make_app()
    app.listen(SERVER_PORT)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
