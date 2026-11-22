from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from django.utils.html import escape
from django.template.loader import render_to_string
from django.conf import settings
import os

ALLOWED_URL_PREFIXES = ('http://', 'https://')

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

# Reference copy of the template rendered by 'profile_template.html'.
PROFILE_TEMPLATE_REFERENCE = """
<html>
<head><title>{{ username }}'s Profile</title></head>
<body>
    <h1>{{ username }}</h1>
    <div class="bio">{{ bio }}</div>
    <p>Website: <a href="{{ website }}">{{ website }}</a></p>
</body>
</html>
"""


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
    """Return the profile with the given username, or None."""
    for profile in profiles:
        if profile.username == username:
            return profile
    return None


def _normalize_website(website):
    """Prefix the website with https:// if it lacks an http(s) scheme."""
    if website and not website.startswith(ALLOWED_URL_PREFIXES):
        return f'https://{website}'
    return website


class ProfileView(View):

    def get(self, request, username):
        profile = _find_profile(username)
        if profile is None:
            return HttpResponse('Profile not found', status=404)
        context = {
            'username': escape(profile.username),
            'bio': escape(profile.bio),
            'website': escape(profile.website),
        }
        return HttpResponse(render_to_string('profile_template.html', context))


class ProfileEditView(View):

    def get(self, request):
        return render(request, 'edit_profile.html')

    def post(self, request):
        username = escape(request.POST.get('username', ''))
        bio = escape(request.POST.get('bio', ''))
        website = _normalize_website(escape(request.POST.get('website', '')))

        global profiles
        profiles = [p for p in profiles if p.username != username]
        profiles.append(UserProfile(username, bio, website))
        return HttpResponse(f'Profile updated for {username}')


def edit_profile_template():
    return EDIT_PROFILE_TEMPLATE


def django_view_dispatcher(request, path):
    if path == 'edit':
        return ProfileEditView.as_view()(request)
    if path.startswith('profile/'):
        username = path.split('/')[1]
        return ProfileView.as_view()(request, username)
    return HttpResponse('Not found', status=404)
