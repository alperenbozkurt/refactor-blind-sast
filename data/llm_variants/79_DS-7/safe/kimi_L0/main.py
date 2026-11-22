import tornado.ioloop
import tornado.web
import tornado.escape
import uuid
import datetime
import json
import html


class Message:

    def __init__(self, sender, content):
        self.id = str(uuid.uuid4())
        self.sender = html.escape(sender)
        self.content = html.escape(content)
        self.timestamp = datetime.datetime.now().isoformat()


class ChatHandler(tornado.web.RequestHandler):
    messages = []

    def get(self):
        if self.request.path == '/messages':
            self.write(self.get_messages_json())
            return

        def line(indent, text=''):
            return ' ' * indent + text

        page_lines = [
            line(0),
            line(8, '<!DOCTYPE html>'),
            line(8, '<html>'),
            line(8, '<head>'),
            line(12, '<title>Chat Room</title>'),
            line(12, '<style>'),
            line(16, '#chat { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: scroll; }'),
            line(16, '.message { margin-bottom: 10px; }'),
            line(16, '.sender { font-weight: bold; }'),
            line(16, '.timestamp { color: #666; font-size: 0.8em; }'),
            line(12, '</style>'),
            line(8, '</head>'),
            line(8, '<body>'),
            line(12, '<h1>Chat Room</h1>'),
            line(12, '<div id="chat"></div>'),
            line(12, '<form id="chat-form">'),
            line(16, '<input type="text" id="sender" placeholder="Your name" required>'),
            line(16, '<input type="text" id="message" placeholder="Your message" required>'),
            line(16, '<button type="submit">Send</button>'),
            line(12, '</form>'),
            line(12, '<script>'),
            line(16, "const chatDiv = document.getElementById('chat');"),
            line(16, "const form = document.getElementById('chat-form');"),
            line(16),
            line(16, 'function escapeHtml(unsafe) {'),
            line(20, 'return unsafe'),
            line(24, '.replace(/&/g, "&amp;")'),
            line(24, '.replace(/</g, "&lt;")'),
            line(24, '.replace(/>/g, "&gt;")'),
            line(24, '.replace(/"/g, "&quot;")'),
            line(24, ".replace(/'/g, \"&#039;\");"),
            line(16, '}'),
            line(16),
            line(16, 'function updateChat() {'),
            line(20, "fetch('/messages')"),
            line(24, '.then(r => r.json())'),
            line(24, '.then(messages => {'),
            line(28, 'chatDiv.innerHTML = messages.map(msg => '),
            line(32, '`<div class="message">'),
            line(36, '<span class="sender">${escapeHtml(msg.sender)}</span>:'),
            line(36, '<span class="content">${escapeHtml(msg.content)}</span>'),
            line(36, '<span class="timestamp">${escapeHtml(msg.timestamp)}</span>'),
            line(32, '</div>`'),
            line(28, ").join('');"),
            line(24, '});'),
            line(16, '}'),
            line(16),
            line(16, "form.addEventListener('submit', (e) => {"),
            line(20, 'e.preventDefault();'),
            line(20, "const sender = document.getElementById('sender').value;"),
            line(20, "const message = document.getElementById('message').value;"),
            line(20),
            line(20, "fetch('/send', {"),
            line(24, "method: 'POST',"),
            line(24, "headers: { 'Content-Type': 'application/json' },"),
            line(24, 'body: JSON.stringify({ sender, message })'),
            line(20, '}).then(() => {'),
            line(24, "document.getElementById('message').value = '';"),
            line(24, 'updateChat();'),
            line(20, '});'),
            line(16, '});'),
            line(16),
            line(16, 'setInterval(updateChat, 1000);'),
            line(16, 'updateChat();'),
            line(12, '</script>'),
            line(8, '</body>'),
            line(8, '</html>'),
            line(8),
        ]
        self.write('\n'.join(page_lines))

    def post(self):
        if self.request.path == '/send':
            try:
                data = json.loads(self.request.body)
                sender = data.get('sender', '')
                message = data.get('message', '')
                if not sender or not message:
                    raise ValueError('Missing sender or message')
                self.messages.append(Message(sender, message))
                self.write({'status': 'ok'})
            except (json.JSONDecodeError, ValueError) as e:
                self.set_status(400)
                self.write({'error': str(e)})
        else:
            self.set_status(404)

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
    return tornado.web.Application([('/', ChatHandler), ('/send', ChatHandler), ('/messages', ChatHandler)])


if __name__ == '__main__':
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
