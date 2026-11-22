from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from django.conf import settings
import os

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

EDIT_ROUTE = 'edit'
PROFILE_ROUTE_PREFIX = 'profile/'

EDIT_PROFILE_TEMPLATE_NAME = 'edit_profile.html'

PROFILE_NOT_FOUND_MESSAGE = 'Profile not found'
NOT_FOUND_MESSAGE = 'Not found'
NOT_FOUND_STATUS = 404

PROFILE_UPDATED_MESSAGE = 'Profile updated for {username}'

PROFILE_HTML_TEMPLATE = (
    '\n'
    '            <html>\n'
    "            <head><title>{profile.username}'s Profile</title></head>\n"
    '            <body>\n'
    '                <h1>{profile.username}</h1>\n'
    '                <div class="bio">{profile.bio}</div>\n'
    '                <p>Website: <a href="{profile.website}">{profile.website}</a></p>\n'
    '            </body>\n'
    '            </html>\n'
    '            '
)

EDIT_PROFILE_HTML = (
    '\n'
    '    <!DOCTYPE html>\n'
    '    <html>\n'
    '    <head>\n'
    '        <title>Edit Profile</title>\n'
    '    </head>\n'
    '    <body>\n'
    '        <h1>Edit Profile</h1>\n'
    '        <form method="POST">\n'
    '            <label>Username: <input type="text" name="username"></label><br>\n'
    '            <label>Bio: <textarea name="bio"></textarea></label><br>\n'
    '            <label>Website: <input type="text" name="website"></label><br>\n'
    '            <button type="submit">Save</button>\n'
    '        </form>\n'
    '    </body>\n'
    '    </html>\n'
    '    '
)


# --------------------------------------------------------------------------
# Model and storage
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


def _find_profile(username):
    """Return the first profile matching ``username`` or None."""
    for profile in profiles:
        if profile.username == username:
            return profile
    return None


def _replace_profile(username, bio, website):
    """Remove any profiles with ``username`` and append a new one."""
    global profiles
    profiles = [p for p in profiles if p.username != username]
    profiles.append(UserProfile(username, bio, website))


def _render_profile(profile):
    return PROFILE_HTML_TEMPLATE.format(profile=profile)


def _extract_username(path):
    return path.split('/')[1]


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------

class ProfileView(View):

    def get(self, request, username):
        profile = _find_profile(username)
        if profile is not None:
            return HttpResponse(_render_profile(profile))
        return HttpResponse(PROFILE_NOT_FOUND_MESSAGE, status=NOT_FOUND_STATUS)


class ProfileEditView(View):

    def get(self, request):
        return render(request, EDIT_PROFILE_TEMPLATE_NAME)

    def post(self, request):
        username = request.POST.get('username')
        bio = request.POST.get('bio')
        website = request.POST.get('website')
        _replace_profile(username, bio, website)
        return HttpResponse(PROFILE_UPDATED_MESSAGE.format(username=username))


def edit_profile_template():
    return EDIT_PROFILE_HTML


def django_view_dispatcher(request, path):
    if path == EDIT_ROUTE:
        return ProfileEditView.as_view()(request)
    elif path.startswith(PROFILE_ROUTE_PREFIX):
        username = _extract_username(path)
        return ProfileView.as_view()(request, username)
    return HttpResponse(NOT_FOUND_MESSAGE, status=NOT_FOUND_STATUS)
