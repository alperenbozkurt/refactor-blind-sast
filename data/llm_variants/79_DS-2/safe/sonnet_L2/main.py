from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from django.utils.html import escape
from django.template.loader import render_to_string
from django.conf import settings
import os

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

PROFILE_TEMPLATE_NAME = 'profile_template.html'
EDIT_PROFILE_TEMPLATE_NAME = 'edit_profile.html'

ALLOWED_URL_SCHEMES = ('http://', 'https://')
DEFAULT_URL_SCHEME = 'https://'

EDIT_PATH = 'edit'
PROFILE_PATH_PREFIX = 'profile/'

PROFILE_NOT_FOUND_MESSAGE = 'Profile not found'
NOT_FOUND_MESSAGE = 'Not found'
NOT_FOUND_STATUS = 404

EDIT_PROFILE_HTML = (
    '\n    <!DOCTYPE html>\n    <html>\n    <head>\n        <title>Edit Profile</title>\n'
    '    </head>\n    <body>\n        <h1>Edit Profile</h1>\n        <form method="POST">\n'
    '            <label>Username: <input type="text" name="username"></label><br>\n'
    '            <label>Bio: <textarea name="bio"></textarea></label><br>\n'
    '            <label>Website: <input type="text" name="website"></label><br>\n'
    '            <button type="submit">Save</button>\n        </form>\n    </body>\n'
    '    </html>\n    '
)

PROFILE_TEMPLATE_HTML = (
    '\n<html>\n<head><title>{{ username }}\'s Profile</title></head>\n<body>\n'
    '    <h1>{{ username }}</h1>\n    <div class="bio">{{ bio }}</div>\n'
    '    <p>Website: <a href="{{ website }}">{{ website }}</a></p>\n</body>\n</html>\n'
)


# --------------------------------------------------------------------------
# Models / storage
# --------------------------------------------------------------------------

class UserProfile:

    def __init__(self, username, bio, website):
        self.username = username
        self.bio = bio
        self.website = website


profiles = [
    UserProfile('admin', 'System administrator', 'https://example.com'),
    UserProfile('user1', 'Regular user', 'https://user1.com'),
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _find_profile(username):
    """Return the profile with the given username, or None."""
    for profile in profiles:
        if profile.username == username:
            return profile
    return None


def _build_profile_context(profile):
    """Build the (escaped) template context for a profile."""
    return {
        'username': escape(profile.username),
        'bio': escape(profile.bio),
        'website': escape(profile.website),
    }


def _read_escaped_post_field(request, name):
    return escape(request.POST.get(name, ''))


def _normalize_website(website):
    """Prefix the website with a default scheme if one is missing."""
    if website and (not website.startswith(ALLOWED_URL_SCHEMES)):
        return f'{DEFAULT_URL_SCHEME}{website}'
    return website


def _replace_profile(profile):
    """Replace any existing profile with the same username by ``profile``."""
    global profiles
    profiles = [p for p in profiles if p.username != profile.username]
    profiles.append(profile)


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------

class ProfileView(View):

    def get(self, request, username):
        profile = _find_profile(username)
        if profile is not None:
            context = _build_profile_context(profile)
            return HttpResponse(render_to_string(PROFILE_TEMPLATE_NAME, context))
        return HttpResponse(PROFILE_NOT_FOUND_MESSAGE, status=NOT_FOUND_STATUS)


class ProfileEditView(View):

    def get(self, request):
        return render(request, EDIT_PROFILE_TEMPLATE_NAME)

    def post(self, request):
        username = _read_escaped_post_field(request, 'username')
        bio = _read_escaped_post_field(request, 'bio')
        website = _normalize_website(_read_escaped_post_field(request, 'website'))
        _replace_profile(UserProfile(username, bio, website))
        return HttpResponse(f'Profile updated for {username}')


def edit_profile_template():
    return EDIT_PROFILE_HTML


def django_view_dispatcher(request, path):
    if path == EDIT_PATH:
        return ProfileEditView.as_view()(request)
    elif path.startswith(PROFILE_PATH_PREFIX):
        username = path.split('/')[1]
        return ProfileView.as_view()(request, username)
    return HttpResponse(NOT_FOUND_MESSAGE, status=NOT_FOUND_STATUS)
