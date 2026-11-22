"""Website screenshot capture tool with a simple interactive CLI."""

import os
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

BROWSER_CHROME = 'chrome'
BROWSER_FIREFOX = 'firefox'
BROWSER_WEBKIT = 'webkit'
SUPPORTED_BROWSERS = (BROWSER_CHROME, BROWSER_FIREFOX, BROWSER_WEBKIT)

DEFAULT_OUTPUT_DIR = 'screenshots'
DEFAULT_BROWSER = BROWSER_CHROME
DEFAULT_DELAY_SECONDS = 2
DEFAULT_CLEANUP_DAYS = 30
SECONDS_PER_DAY = 86400

TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
SCREENSHOT_EXTENSION = '.png'
RASTERIZE_SCRIPT_NAME = 'rasterize.js'

CHROME_BACKEND_COMMAND = 'wkhtmltoimage'
FIREFOX_BACKEND_COMMAND = 'cutycapt'
WEBKIT_BACKEND_COMMAND = 'phantomjs'

MENU_TITLE = '\nWebsite Screenshot Tool:'
MENU_ENTRIES = (
    '1. Capture website screenshot',
    '2. List available screenshots',
    '3. Cleanup old screenshots',
    '4. Exit',
)


class WebsiteScreenshot:
    """Capture and manage website screenshots via external browser backends."""

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_browsers = list(SUPPORTED_BROWSERS)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def generate_filename(self, url):
        domain = urlparse(url).netloc
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return f'{domain}_{timestamp}{SCREENSHOT_EXTENSION}'

    def capture_website(self, url, browser=DEFAULT_BROWSER, delay=DEFAULT_DELAY_SECONDS, full_page=False):
        if not self.validate_url(url):
            raise ValueError('Invalid URL provided')
        output_file = os.path.join(self.output_dir, self.generate_filename(url))
        try:
            command = self._build_capture_command(browser, url, output_file, delay, full_page)
            subprocess.run(command, check=True, stderr=subprocess.PIPE)
            print(f'Screenshot saved to {output_file}')
            return output_file
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode().strip() if e.stderr else str(e)
            raise RuntimeError(f'Screenshot failed: {error_msg}')
        except Exception as e:
            raise RuntimeError(f'Error during screenshot capture: {str(e)}')

    def list_screenshots(self):
        return sorted(
            filename
            for filename in os.listdir(self.output_dir)
            if filename.endswith(SCREENSHOT_EXTENSION)
        )

    def cleanup_screenshots(self, older_than_days=DEFAULT_CLEANUP_DAYS):
        cutoff = datetime.now().timestamp() - older_than_days * SECONDS_PER_DAY
        for filename in os.listdir(self.output_dir):
            filepath = os.path.join(self.output_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old screenshot: {filename}')

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_capture_command(self, browser, url, output_file, delay, full_page):
        if browser == BROWSER_CHROME:
            return self._build_chrome_command(url, output_file, delay, full_page)
        if browser == BROWSER_FIREFOX:
            return self._build_firefox_command(url, output_file, delay)
        return self._build_webkit_command(url, output_file)

    @staticmethod
    def _build_chrome_command(url, output_file, delay, full_page):
        args = [CHROME_BACKEND_COMMAND, '--delay', str(delay)]
        if full_page:
            args.append('--enable-javascript')
        args.extend([url, output_file])
        return args

    @staticmethod
    def _build_firefox_command(url, output_file, delay):
        return [
            FIREFOX_BACKEND_COMMAND,
            f'--url={url}',
            f'--out={output_file}',
            f'--delay={delay}',
        ]

    @staticmethod
    def _build_webkit_command(url, output_file):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        rasterize_script = os.path.join(script_dir, RASTERIZE_SCRIPT_NAME)
        if not os.path.exists(rasterize_script):
            raise FileNotFoundError('rasterize.js script not found')
        return [WEBKIT_BACKEND_COMMAND, rasterize_script, url, output_file]


def print_menu():
    print(MENU_TITLE)
    for entry in MENU_ENTRIES:
        print(entry)
    print('Supported browsers: ' + ', '.join(SUPPORTED_BROWSERS))


def _handle_capture(screenshot_tool):
    url = input('Website URL: ')
    browser = input(f"Browser ({'/'.join(SUPPORTED_BROWSERS)}): ") or DEFAULT_BROWSER
    delay = input(f'Delay in seconds (default {DEFAULT_DELAY_SECONDS}): ') or str(DEFAULT_DELAY_SECONDS)
    full_page = input('Full page (y/n): ').lower() == 'y'
    try:
        screenshot_tool.capture_website(url, browser, int(delay), full_page)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list_screenshots(screenshot_tool):
    screenshots = screenshot_tool.list_screenshots()
    print('Available screenshots:')
    for shot in screenshots:
        print(f'- {shot}')


def _handle_cleanup(screenshot_tool):
    days = input('Delete screenshots older than (days): ') or str(DEFAULT_CLEANUP_DAYS)
    screenshot_tool.cleanup_screenshots(int(days))


def _handle_exit(screenshot_tool):
    print('Exiting...')
    return False


def main():
    screenshot_tool = WebsiteScreenshot()
    handlers = {
        '1': _handle_capture,
        '2': _handle_list_screenshots,
        '3': _handle_cleanup,
        '4': _handle_exit,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
            continue
        if handler(screenshot_tool) is False:
            break


if __name__ == '__main__':
    main()
