import os
import shlex
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
COMMAND_NOT_FOUND_EXIT_CODE = 127

MENU_LINES = (
    '\nWebsite Screenshot Tool:',
    '1. Capture website screenshot',
    '2. List available screenshots',
    '3. Cleanup old screenshots',
    '4. Exit',
    'Supported browsers: ' + ', '.join(SUPPORTED_BROWSERS),
)


def build_capture_command(url, output_file, browser, delay, full_page):
    """Build the argument list for the external screenshot program.

    Arguments are passed as a list (no shell) so that URLs or paths containing
    shell metacharacters cannot be interpreted as commands.
    """
    if browser == 'chrome':
        cmd = ['wkhtmltoimage', '--delay', str(delay)]
        if full_page:
            cmd.append('--enable-javascript')
        cmd.extend([url, output_file])
        return cmd
    if browser == 'firefox':
        return [
            'cutycapt',
            f'--url={url}',
            f'--out={output_file}',
            f'--delay={delay}',
        ]
    return ['phantomjs', 'rasterize.js', url, output_file]


def run_command(cmd):
    """Run a command, raising CalledProcessError on failure (including a missing program)."""
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as exc:
        raise subprocess.CalledProcessError(
            COMMAND_NOT_FOUND_EXIT_CODE, shlex.join(cmd)
        ) from exc


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

    def capture_website(self, url, browser=DEFAULT_BROWSER, delay=DEFAULT_DELAY, full_page=False):
        if not self.validate_url(url):
            raise ValueError('Invalid URL provided')
        output_file = os.path.join(self.output_dir, self.generate_filename(url))
        cmd = build_capture_command(url, output_file, browser, delay, full_page)
        run_command(cmd)
        print(f'Screenshot saved to {output_file}')
        return output_file

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
    for line in MENU_LINES:
        print(line)


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
