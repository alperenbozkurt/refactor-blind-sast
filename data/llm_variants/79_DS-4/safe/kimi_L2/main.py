"""Pyramid-based notification web service.

Exposes endpoints to add notifications, list a user's notifications
(marking them as read in the process), and explicitly mark a user's
notifications as read.
"""

import html
from wsgiref.simple_server import make_server

from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.response import Response
from pyramid.view import view_config

# ---------------------------------------------------------------------------
# Server configuration
# ---------------------------------------------------------------------------

HOST = '0.0.0.0'
PORT = 6543

# ---------------------------------------------------------------------------
# Routing configuration
# ---------------------------------------------------------------------------

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

STATIC_VIEW_NAME = 'static'
STATIC_DIRECTORY = 'static'

JINJA2_PACKAGE = 'pyramid_jinja2'
JINJA2_TEMPLATE_EXTENSION = '.pt'

RENDERER_STRING = 'string'
RENDERER_NOTIFICATIONS = 'templates/notifications.pt'

# ---------------------------------------------------------------------------
# Response messages
# ---------------------------------------------------------------------------

HOME_MESSAGE = 'Welcome to the notification system. Visit /notifications/<user_id>'
MISSING_FIELDS_MESSAGE = 'Both user_id and message are required'
NOTIFICATION_ADDED_MESSAGE = 'Notification added'
NOTIFICATIONS_MARKED_READ_MESSAGE = 'Notifications marked as read'

# Reference copy of ``templates/notifications.pt``. The renderer loads the
# template from disk; this content is kept for documentation purposes only.
NOTIFICATIONS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Notifications for ${user_id}</title>
</head>
<body>
    <h1>Notifications for user ${user_id}</h1>
    <ul>
        % for note in notifications:
            <li class="${'read' if note['read'] else 'unread'}">
                ${note['message']}
            </li>
        % endfor
    </ul>
</body>
</html>
'''


class NotificationSystem:
    """In-memory storage for user notifications."""

    def __init__(self):
        self.notifications = []

    def add_notification(self, user_id, message):
        """Store a new unread notification with HTML-escaped content."""
        self.notifications.append({
            'user_id': self._escape(user_id),
            'message': self._escape(message),
            'read': False,
        })

    def get_user_notifications(self, user_id):
        """Return copies of all notifications belonging to ``user_id``."""
        return [
            {
                'user_id': note['user_id'],
                'message': note['message'],
                'read': note['read'],
            }
            for note in self._notifications_for(user_id)
        ]

    def mark_all_as_read(self, user_id):
        """Mark every notification belonging to ``user_id`` as read."""
        for note in self._notifications_for(user_id):
            note['read'] = True

    def _notifications_for(self, user_id):
        """Return the stored notification dicts matching ``user_id``."""
        clean_user_id = self._escape(user_id)
        return [
            note
            for note in self.notifications
            if note['user_id'] == clean_user_id
        ]

    @staticmethod
    def _escape(value):
        return html.escape(value)


notification_system = NotificationSystem()


@view_config(route_name=ROUTE_HOME, renderer=RENDERER_STRING)
def home_view(request):
    """Render the landing page."""
    return HOME_MESSAGE


@view_config(route_name=ROUTE_ADD_NOTIFICATION, request_method='POST')
def add_notification_view(request):
    """Create a notification from the posted ``user_id`` and ``message``."""
    user_id = request.POST.get('user_id')
    message = request.POST.get('message')
    if not user_id or not message:
        return HTTPBadRequest(MISSING_FIELDS_MESSAGE)
    notification_system.add_notification(user_id, message)
    return Response(NOTIFICATION_ADDED_MESSAGE)


@view_config(route_name=ROUTE_VIEW_NOTIFICATIONS, renderer=RENDERER_NOTIFICATIONS)
def view_notifications_view(request):
    """Render a user's notifications, then mark them as read."""
    user_id = request.matchdict['user_id']
    notifications = notification_system.get_user_notifications(user_id)
    notification_system.mark_all_as_read(user_id)
    return {'user_id': html.escape(user_id), 'notifications': notifications}


@view_config(route_name=ROUTE_MARK_READ, request_method='POST')
def mark_read_view(request):
    """Mark all of a user's notifications as read."""
    user_id = request.matchdict['user_id']
    notification_system.mark_all_as_read(user_id)
    return Response(NOTIFICATIONS_MARKED_READ_MESSAGE)


def _register_routes(config):
    """Register all application routes with the configurator."""
    for route_name, pattern in ROUTES:
        config.add_route(route_name, pattern)


def make_app():
    """Create and configure the WSGI application."""
    with Configurator() as config:
        _register_routes(config)
        config.include(JINJA2_PACKAGE)
        config.add_jinja2_renderer(JINJA2_TEMPLATE_EXTENSION)
        config.add_static_view(name=STATIC_VIEW_NAME, path=STATIC_DIRECTORY)
        config.scan()
    return config.make_wsgi_app()


def main():
    """Start the development server (command-line entry point)."""
    app = make_app()
    server = make_server(HOST, PORT, app)
    server.serve_forever()


if __name__ == '__main__':
    main()
