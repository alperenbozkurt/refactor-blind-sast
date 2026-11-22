"""Flask application for managing and serving web themes.

Themes are stored on disk under a dedicated themes directory. This module
provides routes for serving theme assets and shared static files, a simple
admin page listing the installed themes, and an upload endpoint for theme
installation (not yet implemented). When executed as a script, a set of
sample themes is generated and the development server is started.
"""

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
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

THEMES_DIR = os.path.abspath('/var/www/themes')
STATIC_DIR = os.path.abspath('/var/www/static')
ALLOWED_ASSET_TYPES = {'.css', '.js', '.png', '.jpg', '.gif', '.json'}

# Permission bits applied to directories and files created by this module.
DIRECTORY_MODE = 0o750
FILE_MODE = 0o640

# Sample content generated when running the module as a script.
SAMPLE_THEMES = ['dark', 'light', 'corporate']
SAMPLE_ASSETS = ['css/main.css', 'js/theme.js', 'images/logo.png']
SAMPLE_THEME_VERSION = '1.0'
SAMPLE_THEME_AUTHOR = 'Theme Designer'
MANIFEST_FILENAME = 'theme.json'

# Development server settings used by the command-line entry point.
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

app = Flask(__name__)
app.config['THEMES_DIR'] = THEMES_DIR
app.config['STATIC_DIR'] = STATIC_DIR
app.config['ALLOWED_ASSET_TYPES'] = ALLOWED_ASSET_TYPES


class ThemeManager:
    """Manages on-disk theme storage and safe asset resolution."""

    def __init__(self):
        os.makedirs(app.config['THEMES_DIR'], mode=DIRECTORY_MODE, exist_ok=True)
        os.makedirs(app.config['STATIC_DIR'], mode=DIRECTORY_MODE, exist_ok=True)

    def is_safe_path(self, base_path, requested_path):
        """Return True if requested_path is strictly inside base_path."""
        base_path = os.path.abspath(base_path)
        requested_path = os.path.abspath(requested_path)
        return requested_path.startswith(base_path + os.sep)

    def is_allowed_asset(self, filename):
        """Return True if the filename ends with an allowed extension."""
        if not filename:
            return False
        return any(
            filename.lower().endswith(ext)
            for ext in app.config['ALLOWED_ASSET_TYPES']
        )

    def list_themes(self):
        """Return the names of all valid theme directories."""
        try:
            return [
                name
                for name in os.listdir(app.config['THEMES_DIR'])
                if self._is_theme_directory(name)
            ]
        except Exception as e:
            app.logger.error(f'Error listing themes: {e}')
            return []

    def load_theme(self, theme_name, asset_path):
        """Validate a theme asset request and return its absolute path."""
        if not theme_name or not isinstance(theme_name, str):
            raise ValueError('Invalid theme name')
        safe_theme = secure_filename(theme_name)
        safe_asset = secure_filename(asset_path)
        theme_dir = os.path.join(app.config['THEMES_DIR'], safe_theme)
        asset_full_path = os.path.join(theme_dir, safe_asset)
        self._require_safe_path(
            app.config['THEMES_DIR'], theme_dir, 'Invalid theme path'
        )
        self._require_safe_path(theme_dir, asset_full_path, 'Invalid asset path')
        if not os.path.exists(asset_full_path):
            raise FileNotFoundError('Asset not found')
        if not os.path.isfile(asset_full_path):
            raise ValueError('Requested path is not a file')
        if not self.is_allowed_asset(asset_path):
            raise ValueError('File type not allowed')
        return asset_full_path

    def install_theme(self, zip_file):
        """Install a theme from an uploaded zip file (not implemented)."""
        pass

    # -- internal helpers ----------------------------------------------------

    def _is_theme_directory(self, name):
        """Return True if name is a safe directory inside the themes dir."""
        path = os.path.join(app.config['THEMES_DIR'], name)
        return os.path.isdir(path) and self.is_safe_path(
            app.config['THEMES_DIR'], path
        )

    def _require_safe_path(self, base_path, requested_path, error_message):
        """Raise PermissionError unless requested_path is inside base_path."""
        if not self.is_safe_path(base_path, requested_path):
            raise PermissionError(error_message)


# ---------------------------------------------------------------------------
# Asset routes
# ---------------------------------------------------------------------------

@app.route('/theme/<theme_name>/<path:asset_path>')
def serve_theme_asset(theme_name, asset_path):
    try:
        manager = ThemeManager()
        asset_file = manager.load_theme(theme_name, asset_path)
        return send_file(asset_file)
    except FileNotFoundError:
        abort(404, 'Asset not found')
    except PermissionError:
        abort(403, 'Access denied')
    except ValueError as e:
        abort(400, str(e))
    except Exception:
        abort(500, 'Internal server error')


@app.route('/static/<path:filename>')
def serve_static(filename):
    try:
        manager = ThemeManager()
        if not filename or not isinstance(filename, str):
            abort(400, 'Invalid filename')
        safe_filename = secure_filename(filename)
        static_file = os.path.join(app.config['STATIC_DIR'], safe_filename)
        if not manager.is_safe_path(app.config['STATIC_DIR'], static_file):
            abort(403, 'Access denied')
        if not manager.is_allowed_asset(safe_filename):
            abort(400, 'File type not allowed')
        if not os.path.exists(static_file):
            abort(404, 'File not found')
        return send_file(static_file)
    except Exception:
        abort(500, 'Internal server error')


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route('/admin/themes')
def theme_admin():
    try:
        manager = ThemeManager()
        themes = manager.list_themes()
        return render_template('theme_admin.html', themes=themes)
    except Exception:
        abort(500, 'Internal server error')


@app.route('/admin/themes/upload', methods=['POST'])
def upload_theme():
    if 'theme' not in request.files:
        abort(400, 'No theme file uploaded')
    theme_file = request.files['theme']
    if theme_file.filename == '':
        abort(400, 'No theme file selected')
    try:
        manager = ThemeManager()
        manager.install_theme(theme_file)
        return redirect(url_for('theme_admin'))
    except Exception:
        abort(500, 'Theme installation failed')


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

def _render_error(message, status_code):
    """Render the shared error template for the given status code."""
    return render_template('error.html', error=message), status_code


@app.errorhandler(400)
def bad_request(e):
    return _render_error('Invalid request', 400)


@app.errorhandler(403)
def forbidden(e):
    return _render_error('Access denied', 403)


@app.errorhandler(404)
def not_found(e):
    return _render_error('Resource not found', 404)


@app.errorhandler(500)
def server_error(e):
    return _render_error('Internal server error', 500)


# ---------------------------------------------------------------------------
# Sample data generation and command-line entry point
# ---------------------------------------------------------------------------

def _create_theme_manifest(theme_dir, theme):
    """Write the manifest file for a single sample theme."""
    manifest_path = os.path.join(theme_dir, MANIFEST_FILENAME)
    try:
        with open(manifest_path, 'w') as f:
            json.dump(
                {
                    'name': theme,
                    'version': SAMPLE_THEME_VERSION,
                    'author': SAMPLE_THEME_AUTHOR,
                },
                f,
            )
        os.chmod(manifest_path, FILE_MODE)
    except Exception as e:
        app.logger.error(f'Error creating theme manifest for {theme}: {e}')


def _create_theme_asset(theme_dir, theme, asset):
    """Write a single sample asset file for the given theme."""
    asset_path = os.path.join(theme_dir, asset)
    try:
        os.makedirs(os.path.dirname(asset_path), mode=DIRECTORY_MODE, exist_ok=True)
        with open(asset_path, 'w') as f:
            f.write(f'/* Sample {theme} theme {asset} */')
        os.chmod(asset_path, FILE_MODE)
    except Exception as e:
        app.logger.error(f'Error creating asset {asset} for theme {theme}: {e}')


def _create_sample_theme(theme):
    """Create the directory, manifest and assets for one sample theme."""
    theme_dir = os.path.join(app.config['THEMES_DIR'], theme)
    os.makedirs(theme_dir, mode=DIRECTORY_MODE, exist_ok=True)
    _create_theme_manifest(theme_dir, theme)
    for asset in SAMPLE_ASSETS:
        _create_theme_asset(theme_dir, theme, asset)


def main():
    """Generate the sample themes and start the development server."""
    for theme in SAMPLE_THEMES:
        _create_sample_theme(theme)
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
