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

app = Flask(__name__)
app.config['THEMES_DIR'] = os.path.abspath('/var/www/themes')
app.config['STATIC_DIR'] = os.path.abspath('/var/www/static')
app.config['ALLOWED_ASSET_TYPES'] = {'.css', '.js', '.png', '.jpg', '.gif', '.json'}


class ThemeManager:
    """Handles storage, validation and retrieval of themes and their assets."""

    def __init__(self):
        os.makedirs(app.config['THEMES_DIR'], mode=0o750, exist_ok=True)
        os.makedirs(app.config['STATIC_DIR'], mode=0o750, exist_ok=True)

    def is_safe_path(self, base_path, requested_path):
        """Return True if requested_path resolves to a location inside base_path."""
        base_path = os.path.abspath(base_path)
        requested_path = os.path.abspath(requested_path)
        return requested_path.startswith(base_path + os.sep)

    def is_allowed_asset(self, filename):
        """Return True if the filename has one of the allowed asset extensions."""
        if not filename:
            return False
        lowercase_name = filename.lower()
        return any(
            lowercase_name.endswith(extension)
            for extension in app.config['ALLOWED_ASSET_TYPES']
        )

    def list_themes(self):
        """Return the names of all valid theme directories."""
        try:
            themes = []
            for entry in os.listdir(app.config['THEMES_DIR']):
                entry_path = os.path.join(app.config['THEMES_DIR'], entry)
                if os.path.isdir(entry_path) and self.is_safe_path(
                    app.config['THEMES_DIR'], entry_path
                ):
                    themes.append(entry)
            return themes
        except Exception as e:
            app.logger.error(f'Error listing themes: {e}')
            return []

    def load_theme(self, theme_name, asset_path):
        """Resolve and validate a theme asset, returning its absolute path."""
        if not theme_name or not isinstance(theme_name, str):
            raise ValueError('Invalid theme name')

        safe_theme = secure_filename(theme_name)
        safe_asset = secure_filename(asset_path)
        theme_dir = os.path.join(app.config['THEMES_DIR'], safe_theme)
        asset_full_path = os.path.join(theme_dir, safe_asset)

        if not self.is_safe_path(app.config['THEMES_DIR'], theme_dir):
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
        """Install a theme from an uploaded archive (currently a no-op)."""
        pass


@app.route('/theme/<theme_name>/<path:asset_path>')
def serve_theme_asset(theme_name, asset_path):
    """Serve a single asset belonging to a theme."""
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
    """Serve a file from the shared static directory."""
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
    """Render the theme administration page."""
    try:
        manager = ThemeManager()
        themes = manager.list_themes()
        return render_template('theme_admin.html', themes=themes)
    except Exception:
        abort(500, 'Internal server error')


@app.route('/admin/themes/upload', methods=['POST'])
def upload_theme():
    """Handle theme archive uploads from the admin page."""
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


@app.errorhandler(400)
def bad_request(e):
    return (render_template('error.html', error='Invalid request'), 400)


@app.errorhandler(403)
def forbidden(e):
    return (render_template('error.html', error='Access denied'), 403)


@app.errorhandler(404)
def not_found(e):
    return (render_template('error.html', error='Resource not found'), 404)


@app.errorhandler(500)
def server_error(e):
    return (render_template('error.html', error='Internal server error'), 500)


if __name__ == '__main__':
    sample_themes = ['dark', 'light', 'corporate']
    assets = ['css/main.css', 'js/theme.js', 'images/logo.png']

    for theme in sample_themes:
        theme_dir = os.path.join(app.config['THEMES_DIR'], theme)
        os.makedirs(theme_dir, mode=0o750, exist_ok=True)

        manifest_path = os.path.join(theme_dir, 'theme.json')
        try:
            with open(manifest_path, 'w') as manifest_file:
                json.dump(
                    {'name': theme, 'version': '1.0', 'author': 'Theme Designer'},
                    manifest_file,
                )
            os.chmod(manifest_path, 0o640)
        except Exception as e:
            app.logger.error(f'Error creating theme manifest for {theme}: {e}')

        for asset in assets:
            asset_path = os.path.join(theme_dir, asset)
            try:
                os.makedirs(os.path.dirname(asset_path), mode=0o750, exist_ok=True)
                with open(asset_path, 'w') as asset_file:
                    asset_file.write(f'/* Sample {theme} theme {asset} */')
                os.chmod(asset_path, 0o640)
            except Exception as e:
                app.logger.error(f'Error creating asset {asset} for theme {theme}: {e}')

    app.run(host='0.0.0.0', port=8080)
