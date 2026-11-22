"""Flask application for serving and administering website themes."""

import json
import os

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

app = Flask(__name__)
app.config['THEMES_DIR'] = '/var/www/themes'
app.config['STATIC_DIR'] = '/var/www/static'


class ThemeManager:
    """Filesystem-backed manager for theme directories and their assets."""

    def __init__(self):
        """Ensure the theme and static directories exist."""
        os.makedirs(app.config['THEMES_DIR'], exist_ok=True)
        os.makedirs(app.config['STATIC_DIR'], exist_ok=True)

    def list_themes(self):
        """Return the names of all directories in the themes directory."""
        themes_dir = app.config['THEMES_DIR']
        return [
            name
            for name in os.listdir(themes_dir)
            if os.path.isdir(os.path.join(themes_dir, name))
        ]

    def load_theme(self, theme_name, asset_path):
        """Return the full path to an existing theme asset file.

        Raises:
            FileNotFoundError: If the asset does not exist in the theme.
            ValueError: If the resolved path is not a regular file.
        """
        theme_dir = os.path.join(app.config['THEMES_DIR'], theme_name)
        asset_full_path = os.path.join(theme_dir, asset_path)
        if not os.path.exists(asset_full_path):
            raise FileNotFoundError(
                f'Asset {asset_path} not found in theme {theme_name}'
            )
        if not os.path.isfile(asset_full_path):
            raise ValueError('Requested path is not a file')
        return asset_full_path

    def install_theme(self, zip_file):
        """Install an uploaded theme archive (not yet implemented)."""
        pass


@app.route('/theme/<theme_name>/<path:asset_path>')
def serve_theme_asset(theme_name, asset_path):
    """Serve a single asset belonging to a theme."""
    try:
        manager = ThemeManager()
        asset_file = manager.load_theme(theme_name, asset_path)
        return send_file(asset_file)
    except Exception as e:
        abort(404, str(e))


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve a file from the static directory."""
    static_file = os.path.join(app.config['STATIC_DIR'], filename)
    if not os.path.exists(static_file):
        abort(404, 'File not found')
    return send_file(static_file)


@app.route('/admin/themes')
def theme_admin():
    """Render the theme administration page."""
    manager = ThemeManager()
    themes = manager.list_themes()
    return render_template('theme_admin.html', themes=themes)


@app.route('/admin/themes/upload', methods=['POST'])
def upload_theme():
    """Handle a theme archive upload and redirect to the admin page."""
    if 'theme' not in request.files:
        abort(400, 'No theme file uploaded')
    theme_file = request.files['theme']
    if theme_file.filename == '':
        abort(400, 'No theme file selected')
    try:
        manager = ThemeManager()
        manager.install_theme(theme_file)
        return redirect(url_for('theme_admin'))
    except Exception as e:
        abort(500, str(e))


@app.errorhandler(400)
def bad_request(e):
    """Render the error page for bad requests."""
    return render_template('error.html', error=str(e)), 400


@app.errorhandler(404)
def not_found(e):
    """Render the error page for missing resources."""
    return render_template('error.html', error=str(e)), 404


@app.errorhandler(500)
def server_error(e):
    """Render the error page for internal server errors."""
    return render_template('error.html', error=str(e)), 500


if __name__ == '__main__':
    sample_themes = ['dark', 'light', 'corporate']
    sample_assets = ['css/main.css', 'js/theme.js', 'images/logo.png']
    for theme in sample_themes:
        theme_dir = os.path.join(app.config['THEMES_DIR'], theme)
        os.makedirs(theme_dir, exist_ok=True)

        theme_metadata = {
            'name': theme,
            'version': '1.0',
            'author': 'Theme Designer',
        }
        with open(os.path.join(theme_dir, 'theme.json'), 'w') as metadata_file:
            json.dump(theme_metadata, metadata_file)

        for asset in sample_assets:
            asset_path = os.path.join(theme_dir, asset)
            os.makedirs(os.path.dirname(asset_path), exist_ok=True)
            with open(asset_path, 'w') as asset_file:
                asset_file.write(f'/* Sample {theme} theme {asset} */')

    app.run(host='0.0.0.0', port=8080)
