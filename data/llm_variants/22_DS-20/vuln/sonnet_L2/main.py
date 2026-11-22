import os
import json
from flask import Flask, request, send_file, render_template, abort, redirect, url_for

app = Flask(__name__)
app.config['THEMES_DIR'] = '/var/www/themes'
app.config['STATIC_DIR'] = '/var/www/static'

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
THEMES_DIR_KEY = 'THEMES_DIR'
STATIC_DIR_KEY = 'STATIC_DIR'

THEME_ADMIN_TEMPLATE = 'theme_admin.html'
ERROR_TEMPLATE = 'error.html'
UPLOAD_FIELD_NAME = 'theme'

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

SAMPLE_THEMES = ['dark', 'light', 'corporate']
SAMPLE_THEME_ASSETS = ['css/main.css', 'js/theme.js', 'images/logo.png']
SAMPLE_THEME_METADATA_FILENAME = 'theme.json'
SAMPLE_THEME_VERSION = '1.0'
SAMPLE_THEME_AUTHOR = 'Theme Designer'


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _themes_dir():
    return app.config[THEMES_DIR_KEY]


def _static_dir():
    return app.config[STATIC_DIR_KEY]


def _is_within_directory(base_dir, path):
    """Return True if ``path`` lies inside ``base_dir`` (lexical check).

    Prevents requests from escaping the served directory via ``..`` segments.
    """
    base = os.path.abspath(base_dir)
    target = os.path.abspath(path)
    try:
        return os.path.commonpath([base, target]) == base
    except ValueError:
        return False


def _render_error(e, status_code):
    return (render_template(ERROR_TEMPLATE, error=str(e)), status_code)


# --------------------------------------------------------------------------- #
# Theme management
# --------------------------------------------------------------------------- #
class ThemeManager:

    def __init__(self):
        os.makedirs(_themes_dir(), exist_ok=True)
        os.makedirs(_static_dir(), exist_ok=True)

    def list_themes(self):
        themes_dir = _themes_dir()
        return [
            f for f in os.listdir(themes_dir)
            if os.path.isdir(os.path.join(themes_dir, f))
        ]

    def load_theme(self, theme_name, asset_path):
        theme_dir = os.path.join(_themes_dir(), theme_name)
        asset_full_path = os.path.join(theme_dir, asset_path)
        if not _is_within_directory(theme_dir, asset_full_path) or \
                not _is_within_directory(_themes_dir(), theme_dir):
            raise FileNotFoundError(self._not_found_message(theme_name, asset_path))
        if not os.path.exists(asset_full_path):
            raise FileNotFoundError(self._not_found_message(theme_name, asset_path))
        if not os.path.isfile(asset_full_path):
            raise ValueError('Requested path is not a file')
        return asset_full_path

    def install_theme(self, zip_file):
        pass

    @staticmethod
    def _not_found_message(theme_name, asset_path):
        return f'Asset {asset_path} not found in theme {theme_name}'


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route('/theme/<theme_name>/<path:asset_path>')
def serve_theme_asset(theme_name, asset_path):
    try:
        manager = ThemeManager()
        asset_file = manager.load_theme(theme_name, asset_path)
        return send_file(asset_file)
    except Exception as e:
        abort(404, str(e))


@app.route('/static/<path:filename>')
def serve_static(filename):
    static_file = os.path.join(_static_dir(), filename)
    if not _is_within_directory(_static_dir(), static_file) or \
            not os.path.exists(static_file):
        abort(404, 'File not found')
    return send_file(static_file)


@app.route('/admin/themes')
def theme_admin():
    manager = ThemeManager()
    themes = manager.list_themes()
    return render_template(THEME_ADMIN_TEMPLATE, themes=themes)


@app.route('/admin/themes/upload', methods=['POST'])
def upload_theme():
    if UPLOAD_FIELD_NAME not in request.files:
        abort(400, 'No theme file uploaded')
    theme_file = request.files[UPLOAD_FIELD_NAME]
    if theme_file.filename == '':
        abort(400, 'No theme file selected')
    try:
        manager = ThemeManager()
        manager.install_theme(theme_file)
        return redirect(url_for('theme_admin'))
    except Exception as e:
        abort(500, str(e))


# --------------------------------------------------------------------------- #
# Error handlers
# --------------------------------------------------------------------------- #
@app.errorhandler(400)
def bad_request(e):
    return _render_error(e, 400)


@app.errorhandler(404)
def not_found(e):
    return _render_error(e, 404)


@app.errorhandler(500)
def server_error(e):
    return _render_error(e, 500)


# --------------------------------------------------------------------------- #
# Sample data creation (development entry point)
# --------------------------------------------------------------------------- #
def _write_theme_metadata(theme_dir, theme):
    metadata = {
        'name': theme,
        'version': SAMPLE_THEME_VERSION,
        'author': SAMPLE_THEME_AUTHOR,
    }
    with open(os.path.join(theme_dir, SAMPLE_THEME_METADATA_FILENAME), 'w') as f:
        json.dump(metadata, f)


def _write_sample_asset(theme_dir, theme, asset):
    asset_path = os.path.join(theme_dir, asset)
    os.makedirs(os.path.dirname(asset_path), exist_ok=True)
    with open(asset_path, 'w') as f:
        f.write(f'/* Sample {theme} theme {asset} */')


def _create_sample_theme(theme):
    theme_dir = os.path.join(_themes_dir(), theme)
    os.makedirs(theme_dir, exist_ok=True)
    _write_theme_metadata(theme_dir, theme)
    for asset in SAMPLE_THEME_ASSETS:
        _write_sample_asset(theme_dir, theme, asset)


def _create_sample_themes():
    for theme in SAMPLE_THEMES:
        _create_sample_theme(theme)


def main():
    _create_sample_themes()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
