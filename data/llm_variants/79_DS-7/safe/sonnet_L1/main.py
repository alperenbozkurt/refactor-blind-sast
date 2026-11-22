import tornado.ioloop
import tornado.web
import tornado.escape
import uuid
import datetime
import json
import html

SEND_PATH = '/send'
MESSAGES_PATH = '/messages'
SERVER_PORT = 8888

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
    """A chat message with HTML-escaped sender and content."""

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
            new_message = self._build_message_from_request()
            self.messages.append(new_message)
            self.write({'status': 'ok'})
        except (json.JSONDecodeError, ValueError) as e:
            self.set_status(400)
            self.write({'error': str(e)})

    def _build_message_from_request(self):
        data = json.loads(self.request.body)
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
