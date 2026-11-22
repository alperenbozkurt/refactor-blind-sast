import tornado.ioloop
import tornado.web
import tornado.escape
import uuid
import datetime
import json

_CHAT_PAGE_HTML = '\n        <!DOCTYPE html>\n        <html>\n        <head>\n            <title>Chat Room</title>\n            <style>\n                #chat { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: scroll; }\n                .message { margin-bottom: 10px; }\n                .sender { font-weight: bold; }\n                .timestamp { color: #666; font-size: 0.8em; }\n            </style>\n        </head>\n        <body>\n            <h1>Chat Room</h1>\n            <div id="chat"></div>\n            <form id="chat-form">\n                <input type="text" id="sender" placeholder="Your name" required>\n                <input type="text" id="message" placeholder="Your message" required>\n                <button type="submit">Send</button>\n            </form>\n            <script>\n                const chatDiv = document.getElementById(\'chat\');\n                const form = document.getElementById(\'chat-form\');\n                \n                function updateChat() {\n                    fetch(\'/messages\')\n                        .then(r => r.json())\n                        .then(messages => {\n                            chatDiv.innerHTML = messages.map(msg => \n                                `<div class="message">\n                                    <span class="sender">${msg.sender}</span>:\n                                    <span class="content">${msg.content}</span>\n                                    <span class="timestamp">${msg.timestamp}</span>\n                                </div>`\n                            ).join(\'\');\n                        });\n                }\n                \n                form.addEventListener(\'submit\', (e) => {\n                    e.preventDefault();\n                    const sender = document.getElementById(\'sender\').value;\n                    const message = document.getElementById(\'message\').value;\n                    \n                    fetch(\'/send\', {\n                        method: \'POST\',\n                        headers: { \'Content-Type\': \'application/json\' },\n                        body: JSON.stringify({ sender, message })\n                    }).then(() => {\n                        document.getElementById(\'message\').value = \'\';\n                        updateChat();\n                    });\n                });\n                \n                setInterval(updateChat, 1000);\n                updateChat();\n            </script>\n        </body>\n        </html>\n        '


class Message:

    def __init__(self, sender, content):
        self.id = str(uuid.uuid4())
        self.sender = sender
        self.content = content
        self.timestamp = datetime.datetime.now().isoformat()


class ChatHandler(tornado.web.RequestHandler):
    messages = []

    def get(self):
        if self.request.path == '/messages':
            self.write(self.get_messages_json())
            return
        self.write(_CHAT_PAGE_HTML)

    def post(self):
        if self.request.path != '/send':
            self.set_status(404)
            return

        data = json.loads(self.request.body)
        sender = data['sender']
        message = data['message']

        if sender and message:
            self._store_message(sender, message)
            self.write({'status': 'ok'})
        else:
            self.set_status(400)
            self.write({'error': 'Missing sender or message'})

    def _store_message(self, sender, message):
        new_message = Message(sender, message)
        self.messages.append(new_message)
        return new_message

    def get_messages_json(self):
        return [
            {
                'id': msg.id,
                'sender': msg.sender,
                'content': msg.content,
                'timestamp': msg.timestamp,
            }
            for msg in self.messages
        ]


def make_app():
    return tornado.web.Application([
        ('/', ChatHandler),
        ('/send', ChatHandler),
        ('/messages', ChatHandler),
    ])


if __name__ == '__main__':
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
