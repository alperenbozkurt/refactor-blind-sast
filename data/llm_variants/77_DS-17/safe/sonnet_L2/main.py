import os
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse

DEFAULT_OUTPUT_DIR = 'screenshots'
SUPPORTED_BROWSERS = ('chrome', 'firefox', 'webkit')
DEFAULT_BROWSER = 'chrome'
DEFAULT_DELAY = 2
DEFAULT_CLEANUP_DAYS = 30
SECONDS_PER_DAY = 86400
SCREENSHOT_EXTENSION = '.png'
FILENAME_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
RASTERIZE_SCRIPT_NAME = 'rasterize.js'

WKHTMLTOIMAGE_CMD = 'wkhtmltoimage'
CUTYCAPT_CMD = 'cutycapt'
PHANTOMJS_CMD = 'phantomjs'


def _run_command(args):
    """Run an external command, capturing stderr and raising on failure."""
    subprocess.run(args, check=True, stderr=subprocess.PIPE)


def _format_called_process_error(error):
    """Extract a readable message from a CalledProcessError."""
    return error.stderr.decode().strip() if error.stderr else str(error)


class WebsiteScreenshot:

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
        timestamp = datetime.now().strftime(FILENAME_TIMESTAMP_FORMAT)
        return f'{domain}_{timestamp}{SCREENSHOT_EXTENSION}'

    # ------------------------------------------------------------------
    # Command builders (one per backend)
    # ------------------------------------------------------------------
    @staticmethod
    def _build_wkhtmltoimage_command(url, output_file, delay, full_page):
        args = [WKHTMLTOIMAGE_CMD, '--delay', str(delay)]
        if full_page:
            args.append('--enable-javascript')
        args.extend([url, output_file])
        return args

    @staticmethod
    def _build_cutycapt_command(url, output_file, delay):
        return [
            CUTYCAPT_CMD,
            f'--url={url}',
            f'--out={output_file}',
            f'--delay={delay}',
        ]

    @staticmethod
    def _build_phantomjs_command(url, output_file):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        rasterize_script = os.path.join(script_dir, RASTERIZE_SCRIPT_NAME)
        if not os.path.exists(rasterize_script):
            raise FileNotFoundError('rasterize.js script not found')
        return [PHANTOMJS_CMD, rasterize_script, url, output_file]

    def _build_command(self, url, output_file, browser, delay, full_page):
        if browser == 'chrome':
            return self._build_wkhtmltoimage_command(url, output_file, delay, full_page)
        if browser == 'firefox':
            return self._build_cutycapt_command(url, output_file, delay)
        return self._build_phantomjs_command(url, output_file)

    def capture_website(self, url, browser=DEFAULT_BROWSER, delay=DEFAULT_DELAY, full_page=False):
        if not self.validate_url(url):
            raise ValueError('Invalid URL provided')
        output_file = os.path.join(self.output_dir, self.generate_filename(url))
        try:
            args = self._build_command(url, output_file, browser, delay, full_page)
            _run_command(args)
            print(f'Screenshot saved to {output_file}')
            return output_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Screenshot failed: {_format_called_process_error(e)}')
        except Exception as e:
            raise RuntimeError(f'Error during screenshot capture: {str(e)}')

    def list_screenshots(self):
        return sorted(
            f for f in os.listdir(self.output_dir)
            if f.endswith(SCREENSHOT_EXTENSION)
        )

    def cleanup_screenshots(self, older_than_days=DEFAULT_CLEANUP_DAYS):
        cutoff = datetime.now().timestamp() - older_than_days * SECONDS_PER_DAY
        for filename in os.listdir(self.output_dir):
            filepath = os.path.join(self.output_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old screenshot: {filename}')


def print_menu():
    print('\nWebsite Screenshot Tool:')
    print('1. Capture website screenshot')
    print('2. List available screenshots')
    print('3. Cleanup old screenshots')
    print('4. Exit')
    print('Supported browsers: chrome, firefox, webkit')


def _handle_capture(screenshot_tool):
    url = input('Website URL: ')
    browser = input('Browser (chrome/firefox/webkit): ') or DEFAULT_BROWSER
    delay = input('Delay in seconds (default 2): ') or str(DEFAULT_DELAY)
    full_page = input('Full page (y/n): ').lower() == 'y'
    try:
        screenshot_tool.capture_website(url, browser, int(delay), full_page)
    except Exception as e:
        print(f'Error: {e}')


def _handle_list(screenshot_tool):
    screenshots = screenshot_tool.list_screenshots()
    print('Available screenshots:')
    for shot in screenshots:
        print(f'- {shot}')


def _handle_cleanup(screenshot_tool):
    days = input('Delete screenshots older than (days): ') or str(DEFAULT_CLEANUP_DAYS)
    screenshot_tool.cleanup_screenshots(int(days))


def main():
    screenshot_tool = WebsiteScreenshot()
    handlers = {
        '1': _handle_capture,
        '2': _handle_list,
        '3': _handle_cleanup,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice in handlers:
            handlers[choice](screenshot_tool)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
