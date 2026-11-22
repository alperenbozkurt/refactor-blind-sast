import os
import json
from flask import Flask, request, send_file, render_template, abort, redirect, url_for
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

DEFAULT_THEMES_DIR = '/var/www/themes'
DEFAULT_STATIC_DIR = '/var/www/static'
DEFAULT_ALLOWED_ASSET_TYPES = {'.css', '.js', '.png', '.jpg', '.gif', '.json'}

DIR_MODE = 0o750   # 488
FILE_MODE = 0o640  # 416

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8080

THEME_MANIFEST_NAME = 'theme.json'
SAMPLE_THEMES = ['dark', 'light', 'corporate']
SAMPLE_ASSETS = ['css/main.css', 'js/theme.js', 'images/logo.png']
SAMPLE_MANIFEST_VERSION = '1.0'
SAMPLE_MANIFEST_AUTHOR = 'Theme Designer'

ERROR_TEMPLATE = 'error.html'
ADMIN_TEMPLATE = 'theme_admin.html'


# --------------------------------------------------------------------------
# Application setup
# --------------------------------------------------------------------------

def _apply_default_config(flask_app):
    flask_app.config['THEMES_DIR'] = os.path.abspath(DEFAULT_THEMES_DIR)
    flask_app.config['STATIC_DIR'] = os.path.abspath(DEFAULT_STATIC_DIR)
    flask_app.config['ALLOWED_ASSET_TYPES'] = set(DEFAULT_ALLOWED_ASSET_TYPES)


app = Flask(__name__)
_apply_default_config(app)


# --------------------------------------------------------------------------
# Theme management
# --------------------------------------------------------------------------

class ThemeManager:

    def __init__(self):
        os.makedirs(self._themes_dir(), mode=DIR_MODE, exist_ok=True)
        os.makedirs(self._static_dir(), mode=DIR_MODE, exist_ok=True)

    @staticmethod
    def _themes_dir():
        return app.config['THEMES_DIR']

    @staticmethod
    def _static_dir():
        return app.config['STATIC_DIR']

    @staticmethod
    def _allowed_asset_types():
        return app.config['ALLOWED_ASSET_TYPES']

    def is_safe_path(self, base_path, requested_path):
        base_path = os.path.abspath(base_path)
        requested_path = os.path.abspath(requested_path)
        return requested_path.startswith(base_path + os.sep)

    def is_allowed_asset(self, filename):
        if not filename:
            return False
        lowered = filename.lower()
        return any((lowered.endswith(ext) for ext in self._allowed_asset_types()))

    def _is_valid_theme_entry(self, entry):
        themes_dir = self._themes_dir()
        entry_path = os.path.join(themes_dir, entry)
        return os.path.isdir(entry_path) and self.is_safe_path(themes_dir, entry_path)

    def list_themes(self):
        try:
            return [f for f in os.listdir(self._themes_dir()) if self._is_valid_theme_entry(f)]
        except Exception as e:
            app.logger.error(f'Error listing themes: {e}')
            return []

    def load_theme(self, theme_name, asset_path):
        if not theme_name or not isinstance(theme_name, str):
            raise ValueError('Invalid theme name')
        safe_theme = secure_filename(theme_name)
        safe_asset = secure_filename(asset_path)
        theme_dir = os.path.join(self._themes_dir(), safe_theme)
        asset_full_path = os.path.join(theme_dir, safe_asset)
        if not self.is_safe_path(self._themes_dir(), theme_dir):
            raise PermissionError('Invalid theme path')
        if not self.is_safe_path(theme_dir, asset_full_path):
            raise PermissionError('Invalid asset path')
        if not os.path.exists(asset_full_path):
            raise FileNotFoundError('Asset not found')
        if not os.path.isfile(asset_full_path):
            raise ValueError('Requested path is not a file')
        if not self.is_allowed_asset(asset_path):
            raise ValueError('File type not allowed')
        return asset_full_path

    def install_theme(self, zip_file):
        pass


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

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
    # Note: aborts raised inside the try block are HTTPExceptions and are
    # intentionally caught by the generic handler (resulting in a 500),
    # preserving the original behaviour.
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


@app.route('/admin/themes')
def theme_admin():
    try:
        manager = ThemeManager()
        themes = manager.list_themes()
        return render_template(ADMIN_TEMPLATE, themes=themes)
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


# --------------------------------------------------------------------------
# Error handlers
# --------------------------------------------------------------------------

def _render_error(message, status_code):
    return (render_template(ERROR_TEMPLATE, error=message), status_code)


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


# --------------------------------------------------------------------------
# Sample data generation (development entry point)
# --------------------------------------------------------------------------

def _create_sample_manifest(theme_dir, theme):
    manifest_path = os.path.join(theme_dir, THEME_MANIFEST_NAME)
    try:
        with open(manifest_path, 'w') as f:
            json.dump(
                {
                    'name': theme,
                    'version': SAMPLE_MANIFEST_VERSION,
                    'author': SAMPLE_MANIFEST_AUTHOR,
                },
                f,
            )
        os.chmod(manifest_path, FILE_MODE)
    except Exception as e:
        app.logger.error(f'Error creating theme manifest for {theme}: {e}')


def _create_sample_asset(theme_dir, theme, asset):
    asset_path = os.path.join(theme_dir, asset)
    try:
        os.makedirs(os.path.dirname(asset_path), mode=DIR_MODE, exist_ok=True)
        with open(asset_path, 'w') as f:
            f.write(f'/* Sample {theme} theme {asset} */')
        os.chmod(asset_path, FILE_MODE)
    except Exception as e:
        app.logger.error(f'Error creating asset {asset} for theme {theme}: {e}')


def _create_sample_theme(theme):
    theme_dir = os.path.join(app.config['THEMES_DIR'], theme)
    os.makedirs(theme_dir, mode=DIR_MODE, exist_ok=True)
    _create_sample_manifest(theme_dir, theme)
    for asset in SAMPLE_ASSETS:
        _create_sample_asset(theme_dir, theme, asset)


def create_sample_themes():
    for theme in SAMPLE_THEMES:
        _create_sample_theme(theme)


def main():
    create_sample_themes()
    app.run(host=SERVER_HOST, port=SERVER_PORT)


if __name__ == '__main__':
    main()
