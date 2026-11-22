import tornado.ioloop
import tornado.web
import tornado.escape
import uuid
import datetime
import json

# --- Constants ---------------------------------------------------------------

DEFAULT_PORT = 8888

PATH_INDEX = '/'
PATH_SEND = '/send'
PATH_MESSAGES = '/messages'

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

STATUS_OK_RESPONSE = {'status': 'ok'}
MISSING_FIELDS_RESPONSE = {'error': 'Missing sender or message'}

CHAT_PAGE_HTML = (
    '\n'
    '        <!DOCTYPE html>\n'
    '        <html>\n'
    '        <head>\n'
    '            <title>Chat Room</title>\n'
    '            <style>\n'
    '                #chat { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: scroll; }\n'
    '                .message { margin-bottom: 10px; }\n'
    '                .sender { font-weight: bold; }\n'
    '                .timestamp { color: #666; font-size: 0.8em; }\n'
    '            </style>\n'
    '        </head>\n'
    '        <body>\n'
    '            <h1>Chat Room</h1>\n'
    '            <div id="chat"></div>\n'
    '            <form id="chat-form">\n'
    '                <input type="text" id="sender" placeholder="Your name" required>\n'
    '                <input type="text" id="message" placeholder="Your message" required>\n'
    '                <button type="submit">Send</button>\n'
    '            </form>\n'
    '            <script>\n'
    "                const chatDiv = document.getElementById('chat');\n"
    "                const form = document.getElementById('chat-form');\n"
    '                \n'
    '                function updateChat() {\n'
    "                    fetch('/messages')\n"
    '                        .then(r => r.json())\n'
    '                        .then(messages => {\n'
    '                            chatDiv.innerHTML = messages.map(msg => \n'
    '                                `<div class="message">\n'
    '                                    <span class="sender">${msg.sender}</span>:\n'
    '                                    <span class="content">${msg.content}</span>\n'
    '                                    <span class="timestamp">${msg.timestamp}</span>\n'
    '                                </div>`\n'
    "                            ).join('');\n"
    '                        });\n'
    '                }\n'
    '                \n'
    "                form.addEventListener('submit', (e) => {\n"
    '                    e.preventDefault();\n'
    "                    const sender = document.getElementById('sender').value;\n"
    "                    const message = document.getElementById('message').value;\n"
    '                    \n'
    "                    fetch('/send', {\n"
    "                        method: 'POST',\n"
    "                        headers: { 'Content-Type': 'application/json' },\n"
    '                        body: JSON.stringify({ sender, message })\n'
    '                    }).then(() => {\n'
    "                        document.getElementById('message').value = '';\n"
    '                        updateChat();\n'
    '                    });\n'
    '                });\n'
    '                \n'
    '                setInterval(updateChat, 1000);\n'
    '                updateChat();\n'
    '            </script>\n'
    '        </body>\n'
    '        </html>\n'
    '        '
)


# --- Helpers -----------------------------------------------------------------

def _new_message_id():
    return str(uuid.uuid4())


def _current_timestamp():
    return datetime.datetime.now().isoformat()


def _serialize_message(msg):
    return {
        'id': msg.id,
        'sender': msg.sender,
        'content': msg.content,
        'timestamp': msg.timestamp,
    }


# --- Domain ------------------------------------------------------------------

class Message:

    def __init__(self, sender, content):
        self.id = _new_message_id()
        self.sender = sender
        self.content = content
        self.timestamp = _current_timestamp()


# --- Web layer ---------------------------------------------------------------

class ChatHandler(tornado.web.RequestHandler):
    messages = []

    def get(self):
        if self.request.path == PATH_MESSAGES:
            self.write(self.get_messages_json())
            return
        self.write(CHAT_PAGE_HTML)

    def post(self):
        if self.request.path == PATH_SEND:
            self._handle_send()
        else:
            self.set_status(HTTP_NOT_FOUND)

    def _handle_send(self):
        data = json.loads(self.request.body)
        sender = data['sender']
        message = data['message']
        if sender and message:
            self._store_message(sender, message)
            self.write(STATUS_OK_RESPONSE)
        else:
            self.set_status(HTTP_BAD_REQUEST)
            self.write(MISSING_FIELDS_RESPONSE)

    def _store_message(self, sender, message):
        new_message = Message(sender, message)
        self.messages.append(new_message)
        return new_message

    def get_messages_json(self):
        return [_serialize_message(msg) for msg in self.messages]


def _build_routes():
    return [
        (PATH_INDEX, ChatHandler),
        (PATH_SEND, ChatHandler),
        (PATH_MESSAGES, ChatHandler),
    ]


def make_app():
    return tornado.web.Application(_build_routes())


def main():
    app = make_app()
    app.listen(DEFAULT_PORT)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
