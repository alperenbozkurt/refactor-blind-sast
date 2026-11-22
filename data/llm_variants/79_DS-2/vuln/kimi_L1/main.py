import os

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
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


class ProfileView(View):
    def get(self, request, username):
        def render_profile(profile):
            return f'''
            <html>
            <head><title>{profile.username}'s Profile</title></head>
            <body>
                <h1>{profile.username}</h1>
                <div class="bio">{profile.bio}</div>
                <p>Website: <a href="{profile.website}">{profile.website}</a></p>
            </body>
            </html>
            '''

        profile = next((p for p in profiles if p.username == username), None)
        if profile is None:
            return HttpResponse('Profile not found', status=404)
        return HttpResponse(render_profile(profile))


class ProfileEditView(View):
    def get(self, request):
        return render(request, 'edit_profile.html')

    def post(self, request):
        global profiles

        username = request.POST.get('username')
        bio = request.POST.get('bio')
        website = request.POST.get('website')

        profiles = [p for p in profiles if p.username != username]
        profiles.append(UserProfile(username, bio, website))

        return HttpResponse(f'Profile updated for {username}')


def edit_profile_template():
    return '''
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


def django_view_dispatcher(request, path):
    if path == 'edit':
        return ProfileEditView.as_view()(request)
    if path.startswith('profile/'):
        username = path.split('/')[1]
        return ProfileView.as_view()(request, username)
    return HttpResponse('Not found', status=404)
