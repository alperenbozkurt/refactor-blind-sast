"""User profile pages, editing views and a lightweight request dispatcher.

Profiles are kept in a simple in-memory store and exposed through two
Django class-based views (display / edit) plus a small function-based
dispatcher that routes incoming paths to those views.
"""

import os

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EDIT_PROFILE_TEMPLATE_NAME = 'edit_profile.html'

EDIT_ROUTE = 'edit'
PROFILE_ROUTE_PREFIX = 'profile/'

HTTP_NOT_FOUND = 404

PROFILE_NOT_FOUND_MESSAGE = 'Profile not found'
ROUTE_NOT_FOUND_MESSAGE = 'Not found'
PROFILE_UPDATED_MESSAGE = 'Profile updated for {username}'

PROFILE_PAGE_TEMPLATE = '''
            <html>
            <head><title>{username}'s Profile</title></head>
            <body>
                <h1>{username}</h1>
                <div class="bio">{bio}</div>
                <p>Website: <a href="{website}">{website}</a></p>
            </body>
            </html>
            '''

EDIT_PROFILE_PAGE_TEMPLATE = '''
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
    '''

DEFAULT_PROFILES = (
    ('admin', 'System administrator', 'https://example.com'),
    ('user1', 'Regular user', 'https://user1.com'),
)


class UserProfile:
    """Value object holding the public data of a single user profile."""

    def __init__(self, username, bio, website):
        self.username = username
        self.bio = bio
        self.website = website


def _build_initial_profiles():
    """Create the profiles the application starts with."""
    return [UserProfile(username, bio, website) for username, bio, website in DEFAULT_PROFILES]


profiles = _build_initial_profiles()


def find_profile(username):
    """Return the profile stored under ``username``, or ``None``."""
    for profile in profiles:
        if profile.username == username:
            return profile
    return None


def render_profile(profile):
    """Render the standalone HTML page for ``profile``."""
    return PROFILE_PAGE_TEMPLATE.format(
        username=profile.username,
        bio=profile.bio,
        website=profile.website,
    )


def save_profile(username, bio, website):
    """Create the given profile, replacing any existing one with the same name."""
    global profiles
    profiles = [profile for profile in profiles if profile.username != username]
    profiles.append(UserProfile(username, bio, website))


class ProfileView(View):
    """Render the public profile page for a given username."""

    def get(self, request, username):
        profile = find_profile(username)
        if profile is None:
            return HttpResponse(PROFILE_NOT_FOUND_MESSAGE, status=HTTP_NOT_FOUND)
        return HttpResponse(render_profile(profile))


class ProfileEditView(View):
    """Display the profile edit form and handle its submission."""

    def get(self, request):
        return render(request, EDIT_PROFILE_TEMPLATE_NAME)

    def post(self, request):
        username = request.POST.get('username')
        bio = request.POST.get('bio')
        website = request.POST.get('website')
        save_profile(username, bio, website)
        return HttpResponse(PROFILE_UPDATED_MESSAGE.format(username=username))


def edit_profile_template():
    return EDIT_PROFILE_PAGE_TEMPLATE


def django_view_dispatcher(request, path):
    if path == EDIT_ROUTE:
        return ProfileEditView.as_view()(request)
    elif path.startswith(PROFILE_ROUTE_PREFIX):
        username = path.split('/')[1]
        return ProfileView.as_view()(request, username)
    return HttpResponse(ROUTE_NOT_FOUND_MESSAGE, status=HTTP_NOT_FOUND)
