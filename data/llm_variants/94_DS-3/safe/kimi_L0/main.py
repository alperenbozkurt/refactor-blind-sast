import html
import json
import os

import tornado.ioloop
import tornado.web

FORM_PAGE = """
        <form action="/render" method="post">
            <h1>Template Editor</h1>
            Template Name: <input type="text" name="name"><br>
            Template Content: <br>
            <textarea name="content" rows=10 cols=50></textarea><br>
            <input type="submit" value="Render">
        </form>
        """

RENDERED_PAGE = """
        <h2>Rendered Template: {name}</h2>
        <div style="border:1px solid #ccc; padding:10px;">
            {content}
        </div>
        <a href="/">Back</a>
        """

CONFIG = {"debug": True, "version": "1.0", "features": ["template", "render"]}

ROUTES = [
    ("/", None),  # placeholder, replaced below after class definitions
]


def render_content(content):
    try:
        escaped_content = html.escape(content)
        rendered = escaped_content.replace("\n", "<br>")
        return rendered
    except Exception as e:
        return f"Error: {html.escape(str(e))}"


class MainHandler(tornado.web.RequestHandler):

    def get(self):
        self.write(FORM_PAGE)


class TemplateHandler(tornado.web.RequestHandler):

    def post(self):
        template_name = self.get_body_argument("name")
        template_content = self.get_body_argument("content")

        rendered = render_content(template_content)
        self.write(
            RENDERED_PAGE.format(
                name=html.escape(template_name),
                content=rendered,
            )
        )


class ConfigHandler(tornado.web.RequestHandler):

    def get(self):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(CONFIG))


ROUTES = [
    ("/", MainHandler),
    ("/render", TemplateHandler),
    ("/config", ConfigHandler),
]


def make_app():
    return tornado.web.Application(ROUTES)


if __name__ == "__main__":
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
