from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from wsgiref.simple_server import make_server
import html  # noqa: F401  (kept to preserve module-level names)


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

ROUTE_HOME = 'home'
ROUTE_ADD_NOTIFICATION = 'add_notification'
ROUTE_VIEW_NOTIFICATIONS = 'view_notifications'
ROUTE_MARK_READ = 'mark_read'

ROUTES = (
    (ROUTE_HOME, '/'),
    (ROUTE_ADD_NOTIFICATION, '/add_notification'),
    (ROUTE_VIEW_NOTIFICATIONS, '/notifications/{user_id}'),
    (ROUTE_MARK_READ, '/notifications/{user_id}/mark_read'),
)

HOME_MESSAGE = 'Welcome to the notification system. Visit /notifications/<user_id>'
MSG_NOTIFICATION_ADDED = 'Notification added'
MSG_INVALID_INPUT = 'Invalid input'
MSG_MARKED_READ = 'Notifications marked as read'
HTTP_BAD_REQUEST = 400

STATUS_READ = 'read'
STATUS_UNREAD = 'unread'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 6543


# --------------------------------------------------------------------------- #
# Domain
# --------------------------------------------------------------------------- #

class NotificationSystem:

    def __init__(self):
        self.notifications = []

    def add_notification(self, user_id, message):
        self.notifications.append({'user_id': user_id, 'message': message, 'read': False})

    def get_user_notifications(self, user_id):
        return [n for n in self.notifications if n['user_id'] == user_id]

    def mark_user_notifications_read(self, user_id):
        for note in self.notifications:
            if note['user_id'] == user_id:
                note['read'] = True


notification_system = NotificationSystem()


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #

def _notification_status(note):
    return STATUS_READ if note['read'] else STATUS_UNREAD


def _render_notification_item(note):
    return f"<li class='{_notification_status(note)}'>" + note['message'] + '</li>'


def _render_notifications(user_id, notifications):
    items = ''.join(_render_notification_item(note) for note in notifications)
    return f'<h1>Notifications for user {user_id}</h1><ul>' + items + '</ul>'


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #

@view_config(route_name=ROUTE_HOME, renderer='string')
def home_view(request):
    return HOME_MESSAGE


@view_config(route_name=ROUTE_ADD_NOTIFICATION, request_method='POST')
def add_notification_view(request):
    user_id = request.POST.get('user_id')
    message = request.POST.get('message')
    if user_id and message:
        notification_system.add_notification(user_id, message)
        return Response(MSG_NOTIFICATION_ADDED)
    return Response(MSG_INVALID_INPUT, status=HTTP_BAD_REQUEST)


@view_config(route_name=ROUTE_VIEW_NOTIFICATIONS)
def view_notifications_view(request):
    user_id = request.matchdict['user_id']
    notifications = notification_system.get_user_notifications(user_id)
    return Response(_render_notifications(user_id, notifications))


@view_config(route_name=ROUTE_MARK_READ, request_method='POST')
def mark_read_view(request):
    user_id = request.matchdict['user_id']
    notification_system.mark_user_notifications_read(user_id)
    return Response(MSG_MARKED_READ)


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #

def _add_routes(config):
    for name, pattern in ROUTES:
        config.add_route(name, pattern)


def make_app():
    with Configurator() as config:
        _add_routes(config)
        config.scan()
    return config.make_wsgi_app()


if __name__ == '__main__':
    app = make_app()
    server = make_server(SERVER_HOST, SERVER_PORT, app)
    server.serve_forever()
