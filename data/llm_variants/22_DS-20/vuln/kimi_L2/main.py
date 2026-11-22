"""Flask application for serving and administrating website themes."""

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

# ---------------------------------------------------------------------------
# Application configuration
# ---------------------------------------------------------------------------
THEMES_DIR_CONFIG_KEY = 'THEMES_DIR'
STATIC_DIR_CONFIG_KEY = 'STATIC_DIR'

DEFAULT_THEMES_DIR = '/var/www/themes'
DEFAULT_STATIC_DIR = '/var/www/static'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

# ---------------------------------------------------------------------------
# Theme metadata and sample data
# ---------------------------------------------------------------------------
THEME_METADATA_FILENAME = 'theme.json'
THEME_METADATA_VERSION = '1.0'
THEME_METADATA_AUTHOR = 'Theme Designer'

SAMPLE_THEMES = ('dark', 'light', 'corporate')
SAMPLE_ASSETS = ('css/main.css', 'js/theme.js', 'images/logo.png')
SAMPLE_ASSET_CONTENT_TEMPLATE = '/* Sample {theme} theme {asset} */'

# ---------------------------------------------------------------------------
# Templates, form fields and HTTP status codes
# ---------------------------------------------------------------------------
THEME_ADMIN_TEMPLATE = 'theme_admin.html'
ERROR_TEMPLATE = 'error.html'

UPLOAD_FORM_FIELD = 'theme'
THEME_ADMIN_ENDPOINT = 'theme_admin'

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

# ---------------------------------------------------------------------------
# Error messages
# ---------------------------------------------------------------------------
ERROR_ASSET_NOT_FOUND = 'Asset {asset_path} not found in theme {theme_name}'
ERROR_NOT_A_FILE = 'Requested path is not a file'
ERROR_FILE_NOT_FOUND = 'File not found'
ERROR_NO_THEME_UPLOADED = 'No theme file uploaded'
ERROR_NO_THEME_SELECTED = 'No theme file selected'

app = Flask(__name__)
app.config[THEMES_DIR_CONFIG_KEY] = DEFAULT_THEMES_DIR
app.config[STATIC_DIR_CONFIG_KEY] = DEFAULT_STATIC_DIR


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------
def _themes_dir():
    """Return the configured themes directory."""
    return app.config[THEMES_DIR_CONFIG_KEY]


def _static_dir():
    """Return the configured static directory."""
    return app.config[STATIC_DIR_CONFIG_KEY]


def _ensure_directory(path):
    """Create ``path`` (including parents) if it does not already exist."""
    os.makedirs(path, exist_ok=True)


class ThemeManager:
    """Filesystem-backed manager for installed themes and their assets."""

    def __init__(self):
        _ensure_directory(_themes_dir())
        _ensure_directory(_static_dir())

    def list_themes(self):
        """Return the names of all installed themes."""
        return [
            name
            for name in os.listdir(_themes_dir())
            if self._is_theme_dir(name)
        ]

    def load_theme(self, theme_name, asset_path):
        """Resolve ``asset_path`` within ``theme_name`` to a full file path."""
        asset_full_path = self._asset_full_path(theme_name, asset_path)
        if not os.path.exists(asset_full_path):
            raise FileNotFoundError(
                ERROR_ASSET_NOT_FOUND.format(
                    asset_path=asset_path,
                    theme_name=theme_name,
                )
            )
        if not os.path.isfile(asset_full_path):
            raise ValueError(ERROR_NOT_A_FILE)
        return asset_full_path

    def install_theme(self, zip_file):
        """Install a theme from an uploaded zip archive (not implemented)."""
        pass

    def _theme_dir(self, theme_name):
        return os.path.join(_themes_dir(), theme_name)

    def _asset_full_path(self, theme_name, asset_path):
        return os.path.join(self._theme_dir(theme_name), asset_path)

    def _is_theme_dir(self, name):
        return os.path.isdir(os.path.join(_themes_dir(), name))


# ---------------------------------------------------------------------------
# Asset serving routes
# ---------------------------------------------------------------------------
@app.route('/theme/<theme_name>/<path:asset_path>')
def serve_theme_asset(theme_name, asset_path):
    """Serve a single asset from an installed theme."""
    try:
        manager = ThemeManager()
        asset_file = manager.load_theme(theme_name, asset_path)
        return send_file(asset_file)
    except Exception as e:
        abort(HTTP_NOT_FOUND, str(e))


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve a file from the shared static directory."""
    static_file = os.path.join(_static_dir(), filename)
    if not os.path.exists(static_file):
        abort(HTTP_NOT_FOUND, ERROR_FILE_NOT_FOUND)
    return send_file(static_file)


# ---------------------------------------------------------------------------
# Administration routes
# ---------------------------------------------------------------------------
@app.route('/admin/themes')
def theme_admin():
    """Render the theme administration page."""
    manager = ThemeManager()
    themes = manager.list_themes()
    return render_template(THEME_ADMIN_TEMPLATE, themes=themes)


@app.route('/admin/themes/upload', methods=['POST'])
def upload_theme():
    """Handle theme package uploads from the administration page."""
    if UPLOAD_FORM_FIELD not in request.files:
        abort(HTTP_BAD_REQUEST, ERROR_NO_THEME_UPLOADED)
    theme_file = request.files[UPLOAD_FORM_FIELD]
    if theme_file.filename == '':
        abort(HTTP_BAD_REQUEST, ERROR_NO_THEME_SELECTED)
    try:
        manager = ThemeManager()
        manager.install_theme(theme_file)
        return redirect(url_for(THEME_ADMIN_ENDPOINT))
    except Exception as e:
        abort(HTTP_INTERNAL_SERVER_ERROR, str(e))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
def _render_error(error, status_code):
    """Render the shared error template for the given status code."""
    return (render_template(ERROR_TEMPLATE, error=str(error)), status_code)


@app.errorhandler(HTTP_BAD_REQUEST)
def bad_request(e):
    return _render_error(e, HTTP_BAD_REQUEST)


@app.errorhandler(HTTP_NOT_FOUND)
def not_found(e):
    return _render_error(e, HTTP_NOT_FOUND)


@app.errorhandler(HTTP_INTERNAL_SERVER_ERROR)
def server_error(e):
    return _render_error(e, HTTP_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Sample data generation (development entry point)
# ---------------------------------------------------------------------------
def _sample_theme_metadata(theme_name):
    return {
        'name': theme_name,
        'version': THEME_METADATA_VERSION,
        'author': THEME_METADATA_AUTHOR,
    }


def _write_sample_metadata(theme_dir, theme_name):
    metadata_path = os.path.join(theme_dir, THEME_METADATA_FILENAME)
    with open(metadata_path, 'w') as f:
        json.dump(_sample_theme_metadata(theme_name), f)


def _write_sample_asset(theme_dir, theme_name, asset):
    asset_path = os.path.join(theme_dir, asset)
    _ensure_directory(os.path.dirname(asset_path))
    with open(asset_path, 'w') as f:
        f.write(SAMPLE_ASSET_CONTENT_TEMPLATE.format(theme=theme_name, asset=asset))


def _create_sample_theme(theme_name):
    theme_dir = os.path.join(_themes_dir(), theme_name)
    _ensure_directory(theme_dir)
    _write_sample_metadata(theme_dir, theme_name)
    for asset in SAMPLE_ASSETS:
        _write_sample_asset(theme_dir, theme_name, asset)


def _create_sample_themes():
    for theme_name in SAMPLE_THEMES:
        _create_sample_theme(theme_name)


def main():
    """Seed the sample themes and start the development server."""
    _create_sample_themes()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
