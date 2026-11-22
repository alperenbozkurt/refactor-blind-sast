import tornado.ioloop
import tornado.web
import tornado.escape
import uuid
import datetime
import json
import html

CHAT_PAGE_HTML = '\n        <!DOCTYPE html>\n        <html>\n        <head>\n            <title>Chat Room</title>\n            <style>\n                #chat { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: scroll; }\n                .message { margin-bottom: 10px; }\n                .sender { font-weight: bold; }\n                .timestamp { color: #666; font-size: 0.8em; }\n            </style>\n        </head>\n        <body>\n            <h1>Chat Room</h1>\n            <div id="chat"></div>\n            <form id="chat-form">\n                <input type="text" id="sender" placeholder="Your name" required>\n                <input type="text" id="message" placeholder="Your message" required>\n                <button type="submit">Send</button>\n            </form>\n            <script>\n                const chatDiv = document.getElementById(\'chat\');\n                const form = document.getElementById(\'chat-form\');\n                \n                function escapeHtml(unsafe) {\n                    return unsafe\n                        .replace(/&/g, "&amp;")\n                        .replace(/</g, "&lt;")\n                        .replace(/>/g, "&gt;")\n                        .replace(/"/g, "&quot;")\n                        .replace(/\'/g, "&#039;");\n                }\n                \n                function updateChat() {\n                    fetch(\'/messages\')\n                        .then(r => r.json())\n                        .then(messages => {\n                            chatDiv.innerHTML = messages.map(msg => \n                                `<div class="message">\n                                    <span class="sender">${escapeHtml(msg.sender)}</span>:\n                                    <span class="content">${escapeHtml(msg.content)}</span>\n                                    <span class="timestamp">${escapeHtml(msg.timestamp)}</span>\n                                </div>`\n                            ).join(\'\');\n                        });\n                }\n                \n                form.addEventListener(\'submit\', (e) => {\n                    e.preventDefault();\n                    const sender = document.getElementById(\'sender\').value;\n                    const message = document.getElementById(\'message\').value;\n                    \n                    fetch(\'/send\', {\n                        method: \'POST\',\n                        headers: { \'Content-Type\': \'application/json\' },\n                        body: JSON.stringify({ sender, message })\n                    }).then(() => {\n                        document.getElementById(\'message\').value = \'\';\n                        updateChat();\n                    });\n                });\n                \n                setInterval(updateChat, 1000);\n                updateChat();\n            </script>\n        </body>\n        </html>\n        '

MESSAGES_PATH = '/messages'
SEND_PATH = '/send'
SERVER_PORT = 8888


class Message:

    def __init__(self, sender, content):
        self.id = str(uuid.uuid4())
        self.sender = html.escape(sender)
        self.content = html.escape(content)
        self.timestamp = datetime.datetime.now().isoformat()

    def to_dict(self):
        return {
            'id': self.id,
            'sender': self.sender,
            'content': self.content,
            'timestamp': self.timestamp,
        }


class ChatHandler(tornado.web.RequestHandler):
    messages = []

    def get(self):
        if self.request.path == MESSAGES_PATH:
            self.write(self.get_messages_json())
            return
        self.write(CHAT_PAGE_HTML)

    def post(self):
        if self.request.path != SEND_PATH:
            self.set_status(404)
            return
        try:
            new_message = self._parse_message(self.request.body)
            self.messages.append(new_message)
            self.write({'status': 'ok'})
        except (json.JSONDecodeError, ValueError) as e:
            self.set_status(400)
            self.write({'error': str(e)})

    @staticmethod
    def _parse_message(body):
        data = json.loads(body)
        sender = data.get('sender', '')
        message = data.get('message', '')
        if not sender or not message:
            raise ValueError('Missing sender or message')
        return Message(sender, message)

    def get_messages_json(self):
        return [msg.to_dict() for msg in self.messages]


def make_app():
    return tornado.web.Application([
        ('/', ChatHandler),
        (SEND_PATH, ChatHandler),
        (MESSAGES_PATH, ChatHandler),
    ])


if __name__ == '__main__':
    app = make_app()
    app.listen(SERVER_PORT)
    tornado.ioloop.IOLoop.current().start()
