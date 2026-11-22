"""Minimal Tornado chat room server.

Serves a single-page chat UI at '/' plus a tiny JSON API:

    GET  /messages  -> JSON list of all messages
    POST /send      -> accepts {"sender": ..., "message": ...}
"""

import datetime
import html
import json
import uuid

import tornado.escape
import tornado.ioloop
import tornado.web

# --- Server configuration -------------------------------------------------

DEFAULT_PORT = 8888

INDEX_PATH = '/'
SEND_PATH = '/send'
MESSAGES_PATH = '/messages'

# Front-end page served at INDEX_PATH (rendered verbatim).
CHAT_PAGE_HTML = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Chat Room</title>
            <style>
                #chat { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: scroll; }
                .message { margin-bottom: 10px; }
                .sender { font-weight: bold; }
                .timestamp { color: #666; font-size: 0.8em; }
            </style>
        </head>
        <body>
            <h1>Chat Room</h1>
            <div id="chat"></div>
            <form id="chat-form">
                <input type="text" id="sender" placeholder="Your name" required>
                <input type="text" id="message" placeholder="Your message" required>
                <button type="submit">Send</button>
            </form>
            <script>
                const chatDiv = document.getElementById('chat');
                const form = document.getElementById('chat-form');
                
                function escapeHtml(unsafe) {
                    return unsafe
                        .replace(/&/g, "&amp;")
                        .replace(/</g, "&lt;")
                        .replace(/>/g, "&gt;")
                        .replace(/"/g, "&quot;")
                        .replace(/'/g, "&#039;");
                }
                
                function updateChat() {
                    fetch('/messages')
                        .then(r => r.json())
                        .then(messages => {
                            chatDiv.innerHTML = messages.map(msg => 
                                `<div class="message">
                                    <span class="sender">${escapeHtml(msg.sender)}</span>:
                                    <span class="content">${escapeHtml(msg.content)}</span>
                                    <span class="timestamp">${escapeHtml(msg.timestamp)}</span>
                                </div>`
                            ).join('');
                        });
                }
                
                form.addEventListener('submit', (e) => {
                    e.preventDefault();
                    const sender = document.getElementById('sender').value;
                    const message = document.getElementById('message').value;
                    
                    fetch('/send', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ sender, message })
                    }).then(() => {
                        document.getElementById('message').value = '';
                        updateChat();
                    });
                });
                
                setInterval(updateChat, 1000);
                updateChat();
            </script>
        </body>
        </html>
        """


# --- Domain model -----------------------------------------------------------

class Message:
    """A single chat message with a unique id and a server-side timestamp."""

    def __init__(self, sender, content):
        self.id = str(uuid.uuid4())
        self.sender = html.escape(sender)
        self.content = html.escape(content)
        self.timestamp = datetime.datetime.now().isoformat()


# --- Helpers ----------------------------------------------------------------

def _serialize_message(message):
    """Return the JSON-serializable representation of a Message."""
    return {
        'id': message.id,
        'sender': message.sender,
        'content': message.content,
        'timestamp': message.timestamp,
    }


def _parse_message_payload(body):
    """Parse a raw request body and return a validated (sender, message) pair."""
    data = json.loads(body)
    sender = data.get('sender', '')
    message = data.get('message', '')
    if not sender or not message:
        raise ValueError('Missing sender or message')
    return sender, message


# --- Request handlers ---------------------------------------------------------

class ChatHandler(tornado.web.RequestHandler):
    """Serves the chat page and the JSON message API."""

    messages = []

    def get(self):
        if self.request.path == MESSAGES_PATH:
            self.write(self.get_messages_json())
            return
        self.write(CHAT_PAGE_HTML)

    def post(self):
        if self.request.path == SEND_PATH:
            try:
                sender, message = _parse_message_payload(self.request.body)
                new_message = Message(sender, message)
                self.messages.append(new_message)
                self.write({'status': 'ok'})
            except (json.JSONDecodeError, ValueError) as e:
                self.set_status(400)
                self.write({'error': str(e)})
        else:
            self.set_status(404)

    def get_messages_json(self):
        return [_serialize_message(msg) for msg in self.messages]


# --- Application wiring -------------------------------------------------------

def make_app():
    return tornado.web.Application([
        (INDEX_PATH, ChatHandler),
        (SEND_PATH, ChatHandler),
        (MESSAGES_PATH, ChatHandler),
    ])


def main():
    app = make_app()
    app.listen(DEFAULT_PORT)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
