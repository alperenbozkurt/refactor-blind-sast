from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from wsgiref.simple_server import make_server
import html
from pyramid.httpexceptions import HTTPBadRequest

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

ROUTE_HOME = 'home'
ROUTE_ADD_NOTIFICATION = 'add_notification'
ROUTE_VIEW_NOTIFICATIONS = 'view_notifications'
ROUTE_MARK_READ = 'mark_read'

PATH_HOME = '/'
PATH_ADD_NOTIFICATION = '/add_notification'
PATH_VIEW_NOTIFICATIONS = '/notifications/{user_id}'
PATH_MARK_READ = '/notifications/{user_id}/mark_read'

ROUTES = (
    (ROUTE_HOME, PATH_HOME),
    (ROUTE_ADD_NOTIFICATION, PATH_ADD_NOTIFICATION),
    (ROUTE_VIEW_NOTIFICATIONS, PATH_VIEW_NOTIFICATIONS),
    (ROUTE_MARK_READ, PATH_MARK_READ),
)

NOTIFICATIONS_TEMPLATE = 'templates/notifications.pt'
TEMPLATE_RENDERER_EXTENSION = '.pt'
JINJA2_INCLUDE = 'pyramid_jinja2'
STATIC_VIEW_NAME = 'static'
STATIC_VIEW_PATH = 'static'

HOME_MESSAGE = 'Welcome to the notification system. Visit /notifications/<user_id>'
MISSING_FIELDS_MESSAGE = 'Both user_id and message are required'
NOTIFICATION_ADDED_MESSAGE = 'Notification added'
NOTIFICATIONS_MARKED_READ_MESSAGE = 'Notifications marked as read'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 6543


# --------------------------------------------------------------------------- #
# Domain logic
# --------------------------------------------------------------------------- #

def _clean(value):
    """Sanitise a user-supplied value for storage, comparison and display."""
    return html.escape(value)


class NotificationSystem:

    def __init__(self):
        self.notifications = []

    def add_notification(self, user_id, message):
        clean_user_id = _clean(user_id)
        clean_message = _clean(message)
        self.notifications.append(
            {'user_id': clean_user_id, 'message': clean_message, 'read': False}
        )

    def get_user_notifications(self, user_id):
        clean_user_id = _clean(user_id)
        return [
            self._copy_notification(n)
            for n in self.notifications
            if n['user_id'] == clean_user_id
        ]

    def mark_user_notifications_read(self, user_id):
        clean_user_id = _clean(user_id)
        for note in self.notifications:
            if note['user_id'] == clean_user_id:
                note['read'] = True

    @staticmethod
    def _copy_notification(notification):
        return {
            'user_id': notification['user_id'],
            'message': notification['message'],
            'read': notification['read'],
        }


notification_system = NotificationSystem()


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
    if not user_id or not message:
        return HTTPBadRequest(MISSING_FIELDS_MESSAGE)
    notification_system.add_notification(user_id, message)
    return Response(NOTIFICATION_ADDED_MESSAGE)


@view_config(route_name=ROUTE_VIEW_NOTIFICATIONS, renderer=NOTIFICATIONS_TEMPLATE)
def view_notifications_view(request):
    user_id = request.matchdict['user_id']
    notifications = notification_system.get_user_notifications(user_id)
    notification_system.mark_user_notifications_read(user_id)
    return {'user_id': _clean(user_id), 'notifications': notifications}


@view_config(route_name=ROUTE_MARK_READ, request_method='POST')
def mark_read_view(request):
    user_id = request.matchdict['user_id']
    notification_system.mark_user_notifications_read(user_id)
    return Response(NOTIFICATIONS_MARKED_READ_MESSAGE)


# --------------------------------------------------------------------------- #
# Application setup
# --------------------------------------------------------------------------- #

def _add_routes(config):
    for name, path in ROUTES:
        config.add_route(name, path)


def _configure_renderers(config):
    config.include(JINJA2_INCLUDE)
    config.add_jinja2_renderer(TEMPLATE_RENDERER_EXTENSION)


def make_app():
    with Configurator() as config:
        _add_routes(config)
        _configure_renderers(config)
        config.add_static_view(name=STATIC_VIEW_NAME, path=STATIC_VIEW_PATH)
        config.scan()
    return config.make_wsgi_app()


# Reference copy of the template used by the notifications view.
_NOTIFICATIONS_TEMPLATE_SOURCE = '\n<!DOCTYPE html>\n<html>\n<head>\n    <title>Notifications for ${user_id}</title>\n</head>\n<body>\n    <h1>Notifications for user ${user_id}</h1>\n    <ul>\n        % for note in notifications:\n            <li class="${\'read\' if note[\'read\'] else \'unread\'}">\n                ${note[\'message\']}\n            </li>\n        % endfor\n    </ul>\n</body>\n</html>\n'


def main():
    app = make_app()
    server = make_server(SERVER_HOST, SERVER_PORT, app)
    server.serve_forever()


if __name__ == '__main__':
    app = make_app()
    server = make_server(SERVER_HOST, SERVER_PORT, app)
    server.serve_forever()
