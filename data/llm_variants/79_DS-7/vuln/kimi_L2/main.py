"""A minimal single-room chat server built on top of Tornado.

The module serves a self-contained HTML chat client, accepts new messages
through an HTTP POST endpoint and exposes the accumulated message history
as JSON.
"""

import tornado.ioloop
import tornado.web
import tornado.escape
import uuid
import datetime
import json

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8888

INDEX_PATH = '/'
SEND_PATH = '/send'
MESSAGES_PATH = '/messages'

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

STATUS_OK_RESPONSE = {'status': 'ok'}
MISSING_FIELDS_RESPONSE = {'error': 'Missing sender or message'}

# Self-contained HTML/JS chat client served for GET requests outside
# MESSAGES_PATH. Kept byte-for-byte identical to the original response.
INDEX_HTML = '\n        <!DOCTYPE html>\n        <html>\n        <head>\n            <title>Chat Room</title>\n            <style>\n                #chat { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: scroll; }\n                .message { margin-bottom: 10px; }\n                .sender { font-weight: bold; }\n                .timestamp { color: #666; font-size: 0.8em; }\n            </style>\n        </head>\n        <body>\n            <h1>Chat Room</h1>\n            <div id="chat"></div>\n            <form id="chat-form">\n                <input type="text" id="sender" placeholder="Your name" required>\n                <input type="text" id="message" placeholder="Your message" required>\n                <button type="submit">Send</button>\n            </form>\n            <script>\n                const chatDiv = document.getElementById(\'chat\');\n                const form = document.getElementById(\'chat-form\');\n                \n                function updateChat() {\n                    fetch(\'/messages\')\n                        .then(r => r.json())\n                        .then(messages => {\n                            chatDiv.innerHTML = messages.map(msg => \n                                `<div class="message">\n                                    <span class="sender">${msg.sender}</span>:\n                                    <span class="content">${msg.content}</span>\n                                    <span class="timestamp">${msg.timestamp}</span>\n                                </div>`\n                            ).join(\'\');\n                        });\n                }\n                \n                form.addEventListener(\'submit\', (e) => {\n                    e.preventDefault();\n                    const sender = document.getElementById(\'sender\').value;\n                    const message = document.getElementById(\'message\').value;\n                    \n                    fetch(\'/send\', {\n                        method: \'POST\',\n                        headers: { \'Content-Type\': \'application/json\' },\n                        body: JSON.stringify({ sender, message })\n                    }).then(() => {\n                        document.getElementById(\'message\').value = \'\';\n                        updateChat();\n                    });\n                });\n                \n                setInterval(updateChat, 1000);\n                updateChat();\n            </script>\n        </body>\n        </html>\n        '


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

class Message:
    """A single chat message with a generated id and creation timestamp."""

    def __init__(self, sender, content):
        self.id = str(uuid.uuid4())
        self.sender = sender
        self.content = content
        self.timestamp = datetime.datetime.now().isoformat()

    def to_dict(self):
        """Return the JSON-serialisable representation of this message."""
        return {
            'id': self.id,
            'sender': self.sender,
            'content': self.content,
            'timestamp': self.timestamp,
        }


# ---------------------------------------------------------------------------
# Request handlers
# ---------------------------------------------------------------------------

class ChatHandler(tornado.web.RequestHandler):
    """Serves the chat client plus the message submission/history endpoints."""

    messages = []

    def get(self):
        if self.request.path == MESSAGES_PATH:
            self.write(self.get_messages_json())
            return
        self.write(INDEX_HTML)

    def post(self):
        if self.request.path != SEND_PATH:
            self.set_status(HTTP_NOT_FOUND)
            return

        sender, message = self._parse_send_request()
        if sender and message:
            self.store_message(sender, message)
            self.write(STATUS_OK_RESPONSE)
        else:
            self.set_status(HTTP_BAD_REQUEST)
            self.write(MISSING_FIELDS_RESPONSE)

    def get_messages_json(self):
        return [message.to_dict() for message in self.messages]

    @classmethod
    def store_message(cls, sender, content):
        """Create a new :class:`Message`, store it and return it."""
        new_message = Message(sender, content)
        cls.messages.append(new_message)
        return new_message

    def _parse_send_request(self):
        """Extract the sender and message fields from the JSON request body."""
        data = json.loads(self.request.body)
        return data['sender'], data['message']


# ---------------------------------------------------------------------------
# Application configuration and wiring
# ---------------------------------------------------------------------------

ROUTES = [
    (INDEX_PATH, ChatHandler),
    (SEND_PATH, ChatHandler),
    (MESSAGES_PATH, ChatHandler),
]


class ChatConfig:
    """Configuration object for the chat application."""

    def __init__(self, port=DEFAULT_PORT, routes=None):
        self.port = port
        self.routes = list(ROUTES) if routes is None else list(routes)


DEFAULT_CONFIG = ChatConfig()


def make_app():
    return tornado.web.Application(list(DEFAULT_CONFIG.routes))


def main():
    app = make_app()
    app.listen(DEFAULT_CONFIG.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
