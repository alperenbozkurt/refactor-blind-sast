import tornado.ioloop
import tornado.web
import os
import json
import html

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8888

ROUTE_INDEX = '/'
ROUTE_RENDER = '/render'
ROUTE_CONFIG = '/config'

FIELD_NAME = 'name'
FIELD_CONTENT = 'content'

CONTENT_TYPE_HEADER = 'Content-Type'
JSON_CONTENT_TYPE = 'application/json'

MAIN_PAGE_HTML = (
    '\n        <form action="/render" method="post">\n'
    '            <h1>Template Editor</h1>\n'
    '            Template Name: <input type="text" name="name"><br>\n'
    '            Template Content: <br>\n'
    '            <textarea name="content" rows=10 cols=50></textarea><br>\n'
    '            <input type="submit" value="Render">\n'
    '        </form>\n'
    '        '
)

RENDERED_PAGE_TEMPLATE = (
    '\n        <h2>Rendered Template: {template_name}</h2>\n'
    '        <div style="border:1px solid #ccc; padding:10px;">\n'
    '            {rendered}\n'
    '        </div>\n'
    '        <a href="/">Back</a>\n'
    '        '
)

APP_CONFIG_DEBUG = True
APP_CONFIG_VERSION = '1.0'
APP_CONFIG_FEATURES = ('template', 'render')


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def render_content(content):
    """Escape the content and convert newlines to HTML line breaks."""
    try:
        escaped_content = html.escape(content)
        return escaped_content.replace('\n', '<br>')
    except Exception as e:
        return f'Error: {html.escape(str(e))}'


def build_rendered_page(template_name, rendered):
    """Build the HTML page showing a rendered template."""
    return RENDERED_PAGE_TEMPLATE.format(
        template_name=html.escape(template_name),
        rendered=rendered,
    )


def build_config():
    """Return a fresh configuration dictionary."""
    return {
        'debug': APP_CONFIG_DEBUG,
        'version': APP_CONFIG_VERSION,
        'features': list(APP_CONFIG_FEATURES),
    }


def get_routes():
    """Return the application's routing table."""
    return [
        (ROUTE_INDEX, MainHandler),
        (ROUTE_RENDER, TemplateHandler),
        (ROUTE_CONFIG, ConfigHandler),
    ]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

class MainHandler(tornado.web.RequestHandler):

    def get(self):
        self.write(MAIN_PAGE_HTML)


class TemplateHandler(tornado.web.RequestHandler):

    def post(self):
        template_name = self.get_body_argument(FIELD_NAME)
        template_content = self.get_body_argument(FIELD_CONTENT)
        rendered = render_content(template_content)
        self.write(build_rendered_page(template_name, rendered))


class ConfigHandler(tornado.web.RequestHandler):

    def get(self):
        self.set_header(CONTENT_TYPE_HEADER, JSON_CONTENT_TYPE)
        self.write(json.dumps(build_config()))


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

def make_app():
    return tornado.web.Application(get_routes())


if __name__ == '__main__':
    app = make_app()
    app.listen(DEFAULT_PORT)
    tornado.ioloop.IOLoop.current().start()
