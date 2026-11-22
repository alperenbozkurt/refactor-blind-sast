import os

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.html import escape
from django.views import View


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
    for profile in profiles:
        if profile.username == username:
            return profile
    return None


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
        website = escape(request.POST.get('website', ''))
        if website and not website.startswith(('http://', 'https://')):
            website = f'https://{website}'
        global profiles
        profiles = [p for p in profiles if p.username != username]
        profiles.append(UserProfile(username, bio, website))
        return HttpResponse(f'Profile updated for {username}')


def edit_profile_template():
    return '\n    <!DOCTYPE html>\n    <html>\n    <head>\n        <title>Edit Profile</title>\n    </head>\n    <body>\n        <h1>Edit Profile</h1>\n        <form method="POST">\n            <label>Username: <input type="text" name="username"></label><br>\n            <label>Bio: <textarea name="bio"></textarea></label><br>\n            <label>Website: <input type="text" name="website"></label><br>\n            <button type="submit">Save</button>\n        </form>\n    </body>\n    </html>\n    '


'\n<html>\n<head><title>{{ username }}\'s Profile</title></head>\n<body>\n    <h1>{{ username }}</h1>\n    <div class="bio">{{ bio }}</div>\n    <p>Website: <a href="{{ website }}">{{ website }}</a></p>\n</body>\n</html>\n'


def django_view_dispatcher(request, path):
    if path == 'edit':
        return ProfileEditView.as_view()(request)
    if path.startswith('profile/'):
        username = path.split('/')[1]
        return ProfileView.as_view()(request, username)
    return HttpResponse('Not found', status=404)
