from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from django.conf import settings
import os


class UserProfile:

    def __init__(self, username, bio, website):
        self.username = username
        self.bio = bio
        self.website = website


profiles = [
    UserProfile('admin', 'System administrator', 'https://example.com'),
    UserProfile('user1', 'Regular user', 'https://user1.com'),
]

_PROFILE_INDENT = ' ' * 12

_EDIT_PROFILE_TEMPLATE = (
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


def _render_profile(profile):
    lines = [
        '<html>',
        f"<head><title>{profile.username}'s Profile</title></head>",
        '<body>',
        f'    <h1>{profile.username}</h1>',
        f'    <div class="bio">{profile.bio}</div>',
        f'    <p>Website: <a href="{profile.website}">{profile.website}</a></p>',
        '</body>',
        '</html>',
    ]
    return '\n' + ''.join(f'{_PROFILE_INDENT}{line}\n' for line in lines) + _PROFILE_INDENT


def _find_profile(username):
    for profile in profiles:
        if profile.username == username:
            return profile
    return None


class ProfileView(View):

    def get(self, request, username):
        profile = _find_profile(username)
        if profile is not None:
            return HttpResponse(_render_profile(profile))
        return HttpResponse('Profile not found', status=404)


class ProfileEditView(View):

    def get(self, request):
        return render(request, 'edit_profile.html')

    def post(self, request):
        username = request.POST.get('username')
        bio = request.POST.get('bio')
        website = request.POST.get('website')
        global profiles
        profiles = [p for p in profiles if p.username != username]
        profiles.append(UserProfile(username, bio, website))
        return HttpResponse(f'Profile updated for {username}')


def edit_profile_template():
    return _EDIT_PROFILE_TEMPLATE


def django_view_dispatcher(request, path):
    if path == 'edit':
        return ProfileEditView.as_view()(request)
    if path.startswith('profile/'):
        username = path.split('/')[1]
        return ProfileView.as_view()(request, username)
    return HttpResponse('Not found', status=404)
