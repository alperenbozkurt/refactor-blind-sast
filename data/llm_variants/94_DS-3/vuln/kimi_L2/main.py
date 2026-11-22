"""Minimal Tornado-based template editor and renderer.

Endpoints:

* ``/``        -- serves an HTML form for editing a template.
* ``/render``  -- renders the submitted template content.
* ``/config``  -- returns a static JSON configuration payload.
"""

import json
import os
from dataclasses import dataclass

import tornado.ioloop
import tornado.web


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """Runtime settings for the HTTP server."""

    port: int = 8888


SETTINGS = Settings()

CONTENT_TYPE_HEADER = 'Content-Type'
JSON_CONTENT_TYPE = 'application/json'

APP_CONFIG = {
    'debug': True,
    'version': '1.0',
    'features': ['template', 'render'],
}

ROUTE_MAIN = '/'
ROUTE_RENDER = '/render'
ROUTE_CONFIG = '/config'

FORM_HTML = """
        <form action="/render" method="post">
            <h1>Template Editor</h1>
            Template Name: <input type="text" name="name"><br>
            Template Content: <br>
            <textarea name="content" rows=10 cols=50></textarea><br>
            <input type="submit" value="Render">
        </form>
        """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_template(content):
    """Render *content* as an f-string inside an isolated namespace."""
    locals_dict = {}
    globals_dict = {'__builtins__': None}
    try:
        exec(f"result = f'''{content}'''", globals_dict, locals_dict)
        return locals_dict.get('result', '')
    except Exception as e:
        return str(e)


def _rendered_page_html(template_name, rendered):
    """Build the HTML page displaying a rendered template."""
    return f"""
        <h2>Rendered Template: {template_name}</h2>
        <div style="border:1px solid #ccc; padding:10px;">
            {rendered}
        </div>
        <a href="/">Back</a>
        """


# ---------------------------------------------------------------------------
# Request handlers
# ---------------------------------------------------------------------------

class MainHandler(tornado.web.RequestHandler):

    def get(self):
        self.write(FORM_HTML)


class TemplateHandler(tornado.web.RequestHandler):

    def post(self):
        template_name = self.get_body_argument('name')
        template_content = self.get_body_argument('content')
        rendered = _render_template(template_content)
        self.write(_rendered_page_html(template_name, rendered))


class ConfigHandler(tornado.web.RequestHandler):

    def get(self):
        self.set_header(CONTENT_TYPE_HEADER, JSON_CONTENT_TYPE)
        self.write(json.dumps(APP_CONFIG))


# ---------------------------------------------------------------------------
# Application wiring
# ---------------------------------------------------------------------------

ROUTES = [
    (ROUTE_MAIN, MainHandler),
    (ROUTE_RENDER, TemplateHandler),
    (ROUTE_CONFIG, ConfigHandler),
]


def make_app():
    return tornado.web.Application(ROUTES)


def main():
    app = make_app()
    app.listen(SETTINGS.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
