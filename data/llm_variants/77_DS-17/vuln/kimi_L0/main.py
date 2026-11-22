import os
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse


class WebsiteScreenshot:
    """Capture and manage website screenshots using external tools."""

    SUPPORTED_BROWSERS = ['chrome', 'firefox', 'webkit']
    CHROME = 'chrome'
    FIREFOX = 'firefox'
    SCREENSHOT_EXTENSION = '.png'
    SECONDS_IN_DAY = 86400

    def __init__(self, output_dir='screenshots'):
        self.output_dir = output_dir
        self.supported_browsers = list(self.SUPPORTED_BROWSERS)
        self.create_output_dir()

    def create_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_url(self, url):
        try:
            result = urlparse(url)
        except Exception:
            return False
        return bool(result.scheme and result.netloc)

    def generate_filename(self, url):
        domain = urlparse(url).netloc
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{domain}_{timestamp}.png'

    def capture_website(self, url, browser='chrome', delay=2, full_page=False):
        if not self.validate_url(url):
            raise ValueError('Invalid URL provided')
        output_file = os.path.join(self.output_dir, self.generate_filename(url))
        command = self._build_capture_command(browser, url, output_file, delay, full_page)
        subprocess.run(command, shell=True, check=True)
        print(f'Screenshot saved to {output_file}')
        return output_file

    def _build_capture_command(self, browser, url, output_file, delay, full_page):
        if browser == self.CHROME:
            javascript_flag = '--enable-javascript' if full_page else ''
            return f'wkhtmltoimage --delay {delay} {javascript_flag} {url} {output_file}'
        if browser == self.FIREFOX:
            return f'cutycapt --url={url} --out={output_file} --delay={delay}'
        return f'phantomjs rasterize.js {url} {output_file}'

    def list_screenshots(self):
        return sorted(
            filename
            for filename in os.listdir(self.output_dir)
            if filename.endswith(self.SCREENSHOT_EXTENSION)
        )

    def cleanup_screenshots(self, older_than_days=30):
        cutoff = datetime.now().timestamp() - older_than_days * self.SECONDS_IN_DAY
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
    print(f"Supported browsers: {', '.join(WebsiteScreenshot.SUPPORTED_BROWSERS)}")


def _capture_screenshot(screenshot_tool):
    url = input('Website URL: ')
    browser = input('Browser (chrome/firefox/webkit): ') or 'chrome'
    delay = input('Delay in seconds (default 2): ') or '2'
    full_page = input('Full page (y/n): ').lower() == 'y'
    try:
        screenshot_tool.capture_website(url, browser, int(delay), full_page)
    except Exception as error:
        print(f'Error: {error}')


def _list_screenshots(screenshot_tool):
    print('Available screenshots:')
    for shot in screenshot_tool.list_screenshots():
        print(f'- {shot}')


def _cleanup_screenshots(screenshot_tool):
    days = input('Delete screenshots older than (days): ') or '30'
    screenshot_tool.cleanup_screenshots(int(days))


def main():
    screenshot_tool = WebsiteScreenshot()
    actions = {
        '1': _capture_screenshot,
        '2': _list_screenshots,
        '3': _cleanup_screenshots,
    }
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '4':
            print('Exiting...')
            break
        action = actions.get(choice)
        if action is None:
            print('Invalid choice. Please try again.')
        else:
            action(screenshot_tool)


if __name__ == '__main__':
    main()
