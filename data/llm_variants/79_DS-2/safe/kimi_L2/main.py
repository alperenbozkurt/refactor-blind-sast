import os

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.html import escape
from django.views import View

# Template names used by the views.
PROFILE_TEMPLATE_NAME = 'profile_template.html'
EDIT_PROFILE_TEMPLATE_NAME = 'edit_profile.html'

# HTTP status codes and response messages.
HTTP_NOT_FOUND = 404
PROFILE_NOT_FOUND_MESSAGE = 'Profile not found'
NOT_FOUND_MESSAGE = 'Not found'
PROFILE_UPDATED_MESSAGE = 'Profile updated for {username}'

# Website URL normalization.
WEBSITE_SCHEMES = ('http://', 'https://')
DEFAULT_WEBSITE_SCHEME = 'https://'

# Paths recognised by the view dispatcher.
EDIT_PATH = 'edit'
PROFILE_PATH_PREFIX = 'profile/'

EDIT_PROFILE_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Edit Profile</title>
    </head>
    <body>
        <h1>Edit Profile</h1>
        <form method="POST">
            <label>Username: <input type="text" name="username"></label><br>
            <label>Bio: <textarea name="bio"></textarea></label><br>
            <label>Website: <input type="text" name="website"></label><br>
            <button type="submit">Save</button>
        </form>
    </body>
    </html>
    """

PROFILE_TEMPLATE = """
<html>
<head><title>{{ username }}'s Profile</title></head>
<body>
    <h1>{{ username }}</h1>
    <div class="bio">{{ bio }}</div>
    <p>Website: <a href="{{ website }}">{{ website }}</a></p>
</body>
</html>
"""

# Seed data for the in-memory profile store.
DEFAULT_PROFILES = (
    ('admin', 'System administrator', 'https://example.com'),
    ('user1', 'Regular user', 'https://user1.com'),
)


class UserProfile:

    def __init__(self, username, bio, website):
        self.username = username
        self.bio = bio
        self.website = website


profiles = [UserProfile(*fields) for fields in DEFAULT_PROFILES]


def _find_profile(username):
    """Return the profile stored under ``username``, or ``None``."""
    for profile in profiles:
        if profile.username == username:
            return profile
    return None


def _profile_context(profile):
    """Build the escaped template context for ``profile``."""
    return {
        'username': escape(profile.username),
        'bio': escape(profile.bio),
        'website': escape(profile.website),
    }


def _escaped_profile_data(request):
    """Extract and escape the profile fields from a POST request."""
    username = escape(request.POST.get('username', ''))
    bio = escape(request.POST.get('bio', ''))
    website = escape(request.POST.get('website', ''))
    return username, bio, website


def _normalize_website(website):
    """Prefix ``website`` with the default scheme unless it already has one."""
    if website and not website.startswith(WEBSITE_SCHEMES):
        return f'{DEFAULT_WEBSITE_SCHEME}{website}'
    return website


def _save_profile(profile):
    """Replace any stored profile that has the same username."""
    global profiles
    profiles = [p for p in profiles if p.username != profile.username]
    profiles.append(profile)


class ProfileView(View):

    def get(self, request, username):
        profile = _find_profile(username)
        if profile is None:
            return HttpResponse(PROFILE_NOT_FOUND_MESSAGE, status=HTTP_NOT_FOUND)
        context = _profile_context(profile)
        return HttpResponse(render_to_string(PROFILE_TEMPLATE_NAME, context))


class ProfileEditView(View):

    def get(self, request):
        return render(request, EDIT_PROFILE_TEMPLATE_NAME)

    def post(self, request):
        username, bio, website = _escaped_profile_data(request)
        website = _normalize_website(website)
        _save_profile(UserProfile(username, bio, website))
        return HttpResponse(PROFILE_UPDATED_MESSAGE.format(username=username))


def edit_profile_template():
    return EDIT_PROFILE_TEMPLATE


def django_view_dispatcher(request, path):
    if path == EDIT_PATH:
        return ProfileEditView.as_view()(request)
    if path.startswith(PROFILE_PATH_PREFIX):
        username = path.split('/')[1]
        return ProfileView.as_view()(request, username)
    return HttpResponse(NOT_FOUND_MESSAGE, status=HTTP_NOT_FOUND)
