"""Command-line tool for capturing and managing website screenshots."""

import os
import subprocess
import sys  # noqa: F401  # retained for backward compatibility of module namespace
from datetime import datetime
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = 'screenshots'
DEFAULT_BROWSER = 'chrome'
DEFAULT_DELAY_SECONDS = 2
DEFAULT_CLEANUP_DAYS = 30

SECONDS_PER_DAY = 86400
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
SCREENSHOT_EXTENSION = '.png'

SUPPORTED_BROWSERS = ('chrome', 'firefox', 'webkit')

CHROME_FULL_PAGE_FLAG = '--enable-javascript'
CHROME_COMMAND_TEMPLATE = 'wkhtmltoimage --delay {delay} {flag} {url} {output_file}'
FIREFOX_COMMAND_TEMPLATE = 'cutycapt --url={url} --out={output_file} --delay={delay}'
FALLBACK_COMMAND_TEMPLATE = 'phantomjs rasterize.js {url} {output_file}'

BROWSER_PROMPT = 'Browser ({}): '.format('/'.join(SUPPORTED_BROWSERS))
DELAY_PROMPT = 'Delay in seconds (default {}): '.format(DEFAULT_DELAY_SECONDS)
CLEANUP_PROMPT = 'Delete screenshots older than (days): '

MENU_TITLE = '\nWebsite Screenshot Tool:'
MENU_OPTIONS = (
    '1. Capture website screenshot',
    '2. List available screenshots',
    '3. Cleanup old screenshots',
    '4. Exit',
)

CHOICE_CAPTURE = '1'
CHOICE_LIST = '2'
CHOICE_CLEANUP = '3'
CHOICE_EXIT = '4'


class WebsiteScreenshot:
    """Capture website screenshots and manage the screenshot directory."""

    def __init__(self, output_dir='screenshots'):
        self.output_dir = output_dir
        self.supported_browsers = list(SUPPORTED_BROWSERS)
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not already exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_url(self, url):
        """Return True when *url* has both a scheme and a network location."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def generate_filename(self, url):
        """Build a timestamped screenshot filename based on the URL domain."""
        domain = urlparse(url).netloc
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        return f'{domain}_{timestamp}{SCREENSHOT_EXTENSION}'

    def capture_website(self, url, browser='chrome', delay=2, full_page=False):
        """Capture a screenshot of *url* using the selected external tool."""
        if not self.validate_url(url):
            raise ValueError('Invalid URL provided')
        output_file = os.path.join(self.output_dir, self.generate_filename(url))
        cmd = self._build_capture_command(url, output_file, browser, delay, full_page)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Screenshot saved to {output_file}')
        return output_file

    def list_screenshots(self):
        """Return the sorted names of all PNG files in the output directory."""
        return sorted(
            filename
            for filename in os.listdir(self.output_dir)
            if filename.endswith(SCREENSHOT_EXTENSION)
        )

    def cleanup_screenshots(self, older_than_days=30):
        """Delete screenshots older than *older_than_days* days."""
        cutoff = datetime.now().timestamp() - older_than_days * SECONDS_PER_DAY
        for filename in os.listdir(self.output_dir):
            filepath = os.path.join(self.output_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old screenshot: {filename}')

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_capture_command(self, url, output_file, browser, delay, full_page):
        """Return the shell command for the requested browser."""
        if browser == 'chrome':
            return self._build_chrome_command(url, output_file, delay, full_page)
        if browser == 'firefox':
            return FIREFOX_COMMAND_TEMPLATE.format(
                url=url, output_file=output_file, delay=delay
            )
        return FALLBACK_COMMAND_TEMPLATE.format(url=url, output_file=output_file)

    @staticmethod
    def _build_chrome_command(url, output_file, delay, full_page):
        flag = CHROME_FULL_PAGE_FLAG if full_page else ''
        return CHROME_COMMAND_TEMPLATE.format(
            delay=delay, flag=flag, url=url, output_file=output_file
        )


def print_menu():
    """Print the interactive menu."""
    print(MENU_TITLE)
    for option in MENU_OPTIONS:
        print(option)
    print('Supported browsers: {}'.format(', '.join(SUPPORTED_BROWSERS)))


def _handle_capture(screenshot_tool):
    url = input('Website URL: ')
    browser = input(BROWSER_PROMPT) or DEFAULT_BROWSER
    delay = input(DELAY_PROMPT) or str(DEFAULT_DELAY_SECONDS)
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
    days = input(CLEANUP_PROMPT) or str(DEFAULT_CLEANUP_DAYS)
    screenshot_tool.cleanup_screenshots(int(days))


def main():
    """Run the interactive command-line interface."""
    screenshot_tool = WebsiteScreenshot()
    handlers = {
        CHOICE_CAPTURE: _handle_capture,
        CHOICE_LIST: _handle_list,
        CHOICE_CLEANUP: _handle_cleanup,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == CHOICE_EXIT:
            print('Exiting...')
            break
        handler = handlers.get(choice)
        if handler is None:
            print('Invalid choice. Please try again.')
        else:
            handler(screenshot_tool)


if __name__ == '__main__':
    main()
