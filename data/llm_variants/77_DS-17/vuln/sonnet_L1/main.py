import os
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse

DEFAULT_OUTPUT_DIR = 'screenshots'
SECONDS_PER_DAY = 86400
TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'


class WebsiteScreenshot:

    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.supported_browsers = ['chrome', 'firefox', 'webkit']
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
        return f'{domain}_{timestamp}.png'

    def _build_command(self, url, output_file, browser, delay, full_page):
        # NOTE: the command is intentionally built as a string and run through
        # the shell, exactly as in the original implementation.
        if browser == 'chrome':
            javascript_flag = '--enable-javascript' if full_page else ''
            return f"wkhtmltoimage --delay {delay} {javascript_flag} {url} {output_file}"
        if browser == 'firefox':
            return f'cutycapt --url={url} --out={output_file} --delay={delay}'
        return f'phantomjs rasterize.js {url} {output_file}'

    def capture_website(self, url, browser='chrome', delay=2, full_page=False):
        if not self.validate_url(url):
            raise ValueError('Invalid URL provided')
        output_file = os.path.join(self.output_dir, self.generate_filename(url))
        cmd = self._build_command(url, output_file, browser, delay, full_page)
        subprocess.run(cmd, shell=True, check=True)
        print(f'Screenshot saved to {output_file}')
        return output_file

    def list_screenshots(self):
        return sorted(f for f in os.listdir(self.output_dir) if f.endswith('.png'))

    def cleanup_screenshots(self, older_than_days=30):
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


def handle_capture(screenshot_tool):
    url = input('Website URL: ')
    browser = input('Browser (chrome/firefox/webkit): ') or 'chrome'
    delay = input('Delay in seconds (default 2): ') or '2'
    full_page = input('Full page (y/n): ').lower() == 'y'
    try:
        screenshot_tool.capture_website(url, browser, int(delay), full_page)
    except Exception as e:
        print(f'Error: {e}')


def handle_list(screenshot_tool):
    screenshots = screenshot_tool.list_screenshots()
    print('Available screenshots:')
    for shot in screenshots:
        print(f'- {shot}')


def handle_cleanup(screenshot_tool):
    days = input('Delete screenshots older than (days): ') or '30'
    screenshot_tool.cleanup_screenshots(int(days))


def main():
    screenshot_tool = WebsiteScreenshot()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            handle_capture(screenshot_tool)
        elif choice == '2':
            handle_list(screenshot_tool)
        elif choice == '3':
            handle_cleanup(screenshot_tool)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
