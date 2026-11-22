"""Simple Pyramid-based notification system."""

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from wsgiref.simple_server import make_server
import html

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 6543

ROUTE_HOME = 'home'
ROUTE_ADD_NOTIFICATION = 'add_notification'
ROUTE_VIEW_NOTIFICATIONS = 'view_notifications'
ROUTE_MARK_READ = 'mark_read'

PATH_HOME = '/'
PATH_ADD_NOTIFICATION = '/add_notification'
PATH_VIEW_NOTIFICATIONS = '/notifications/{user_id}'
PATH_MARK_READ = '/notifications/{user_id}/mark_read'

# Routes are registered in this exact order.
ROUTES = (
    (ROUTE_HOME, PATH_HOME),
    (ROUTE_ADD_NOTIFICATION, PATH_ADD_NOTIFICATION),
    (ROUTE_VIEW_NOTIFICATIONS, PATH_VIEW_NOTIFICATIONS),
    (ROUTE_MARK_READ, PATH_MARK_READ),
)

# ---------------------------------------------------------------------------
# Messages and labels
# ---------------------------------------------------------------------------

HOME_MESSAGE = 'Welcome to the notification system. Visit /notifications/<user_id>'
NOTIFICATION_ADDED_MESSAGE = 'Notification added'
INVALID_INPUT_MESSAGE = 'Invalid input'
NOTIFICATIONS_MARKED_READ_MESSAGE = 'Notifications marked as read'

STATUS_READ = 'read'
STATUS_UNREAD = 'unread'

STATUS_BAD_REQUEST = 400


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

class NotificationSystem:

    def __init__(self):
        self.notifications = []

    @staticmethod
    def _build_notification(user_id, message):
        return {'user_id': user_id, 'message': message, 'read': False}

    def add_notification(self, user_id, message):
        self.notifications.append(self._build_notification(user_id, message))

    def get_user_notifications(self, user_id):
        return [n for n in self.notifications if n['user_id'] == user_id]

    def mark_all_as_read(self, user_id):
        for note in self.notifications:
            if note['user_id'] == user_id:
                note['read'] = True


notification_system = NotificationSystem()


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _notification_status(note):
    return STATUS_READ if note['read'] else STATUS_UNREAD


def _render_notification_item(note):
    return f"<li class='{_notification_status(note)}'>" + note['message'] + '</li>'


def _render_notifications(user_id, notifications):
    parts = [f'<h1>Notifications for user {user_id}</h1><ul>']
    for note in notifications:
        parts.append(_render_notification_item(note))
    parts.append('</ul>')
    return ''.join(parts)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@view_config(route_name=ROUTE_HOME, renderer='string')
def home_view(request):
    return HOME_MESSAGE


@view_config(route_name=ROUTE_ADD_NOTIFICATION, request_method='POST')
def add_notification_view(request):
    user_id = request.POST.get('user_id')
    message = request.POST.get('message')
    if user_id and message:
        notification_system.add_notification(user_id, message)
        return Response(NOTIFICATION_ADDED_MESSAGE)
    return Response(INVALID_INPUT_MESSAGE, status=STATUS_BAD_REQUEST)


@view_config(route_name=ROUTE_VIEW_NOTIFICATIONS)
def view_notifications_view(request):
    user_id = request.matchdict['user_id']
    notifications = notification_system.get_user_notifications(user_id)
    return Response(_render_notifications(user_id, notifications))


@view_config(route_name=ROUTE_MARK_READ, request_method='POST')
def mark_read_view(request):
    user_id = request.matchdict['user_id']
    notification_system.mark_all_as_read(user_id)
    return Response(NOTIFICATIONS_MARKED_READ_MESSAGE)


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

def make_app():
    with Configurator() as config:
        for route_name, path in ROUTES:
            config.add_route(route_name, path)
        config.scan()
    return config.make_wsgi_app()


def main():
    app = make_app()
    server = make_server(SERVER_HOST, SERVER_PORT, app)
    server.serve_forever()


if __name__ == '__main__':
    main()
