"""Minimal Tornado-based chat room.

Serves a single-page chat UI at '/', accepts new messages via POST
requests to '/send', and returns all stored messages as JSON at
'/messages'.
"""

import datetime
import html
import json
import uuid

import tornado.escape
import tornado.ioloop
import tornado.web

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


class Message:
    """A single chat message.

    The sender and content are HTML-escaped upon creation. Each message
    receives a random UUID and an ISO 8601 creation timestamp.
    """

    def __init__(self, sender, content):
        self.id = str(uuid.uuid4())
        self.sender = html.escape(sender)
        self.content = html.escape(content)
        self.timestamp = datetime.datetime.now().isoformat()


class ChatHandler(tornado.web.RequestHandler):
    """Serves the chat page and handles message storage and retrieval."""

    # Class-level store shared by all handler instances.
    messages = []

    def get(self):
        if self.request.path == '/messages':
            self.write(self.get_messages_json())
            return
        self.write(CHAT_PAGE_HTML)

    def post(self):
        if self.request.path != '/send':
            self.set_status(404)
            return
        try:
            data = json.loads(self.request.body)
            sender = data.get('sender', '')
            message = data.get('message', '')
            if not sender or not message:
                raise ValueError('Missing sender or message')
            new_message = Message(sender, message)
            self.messages.append(new_message)
            self.write({'status': 'ok'})
        except (json.JSONDecodeError, ValueError) as e:
            self.set_status(400)
            self.write({'error': str(e)})

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


def main():
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
