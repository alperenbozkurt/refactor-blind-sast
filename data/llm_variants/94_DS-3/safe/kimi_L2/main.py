"""Template editor web application built on Tornado.

Serves a small HTML form for editing templates, renders escaped template
content, and exposes a JSON configuration endpoint.
"""

import html
import json
import os  # noqa: F401  (retained as part of the public module namespace)
from dataclasses import dataclass

import tornado.ioloop
import tornado.web


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServerConfig:
    """Runtime configuration for the HTTP server."""

    port: int = 8888


SERVER_CONFIG = ServerConfig()

JSON_CONTENT_TYPE = 'application/json'

APP_CONFIG = {
    'debug': True,
    'version': '1.0',
    'features': ['template', 'render'],
}

EDITOR_PAGE = (
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


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def render_template_content(content):
    """Return HTML-escaped *content* with newlines converted to <br> tags."""
    try:
        escaped_content = html.escape(content)
        rendered = escaped_content.replace('\n', '<br>')
        return rendered
    except Exception as e:
        return f'Error: {html.escape(str(e))}'


def build_rendered_page(template_name, rendered):
    """Build the HTML page displaying a rendered template."""
    return (
        f'\n'
        f'        <h2>Rendered Template: {html.escape(template_name)}</h2>\n'
        f'        <div style="border:1px solid #ccc; padding:10px;">\n'
        f'            {rendered}\n'
        f'        </div>\n'
        f'        <a href="/">Back</a>\n'
        f'        '
    )


# ---------------------------------------------------------------------------
# Request handlers
# ---------------------------------------------------------------------------

class MainHandler(tornado.web.RequestHandler):

    def get(self):
        self.write(EDITOR_PAGE)


class TemplateHandler(tornado.web.RequestHandler):

    def post(self):
        template_name = self.get_body_argument('name')
        template_content = self.get_body_argument('content')
        rendered = render_template_content(template_content)
        self.write(build_rendered_page(template_name, rendered))


class ConfigHandler(tornado.web.RequestHandler):

    def get(self):
        self.set_header('Content-Type', JSON_CONTENT_TYPE)
        self.write(json.dumps(APP_CONFIG))


# ---------------------------------------------------------------------------
# Application wiring
# ---------------------------------------------------------------------------

ROUTES = [
    ('/', MainHandler),
    ('/render', TemplateHandler),
    ('/config', ConfigHandler),
]


def make_app():
    return tornado.web.Application(ROUTES)


def main():
    app = make_app()
    app.listen(SERVER_CONFIG.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
