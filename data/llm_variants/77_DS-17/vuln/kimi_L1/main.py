"""Interactive command-line tool for capturing and managing website screenshots."""

import os
import subprocess
import sys
from datetime import datetime, timedelta
from urllib.parse import urlparse


class WebsiteScreenshot:
    """Capture website screenshots using external browser-based tools.

    Screenshots are stored as PNG files in ``output_dir``. The supported
    browser backends are ``chrome`` (wkhtmltoimage), ``firefox``
    (cutycapt) and ``webkit`` (phantomjs).
    """

    def __init__(self, output_dir='screenshots'):
        self.output_dir = output_dir
        self.supported_browsers = ['chrome', 'firefox', 'webkit']
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not exist yet."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_url(self, url):
        """Return True if *url* contains both a scheme and a network location."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def generate_filename(self, url):
        """Return a timestamped PNG filename derived from the domain of *url*."""
        domain = urlparse(url).netloc
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{domain}_{timestamp}.png'

    def capture_website(self, url, browser='chrome', delay=2, full_page=False):
        """Capture a screenshot of *url* and return the path of the saved file.

        Raises ValueError if *url* is not a valid URL.
        """
        if not self.validate_url(url):
            raise ValueError('Invalid URL provided')

        output_file = os.path.join(self.output_dir, self.generate_filename(url))

        if browser == 'chrome':
            javascript_flag = '--enable-javascript' if full_page else ''
            cmd = f'wkhtmltoimage --delay {delay} {javascript_flag} {url} {output_file}'
        elif browser == 'firefox':
            cmd = f'cutycapt --url={url} --out={output_file} --delay={delay}'
        else:
            cmd = f'phantomjs rasterize.js {url} {output_file}'

        subprocess.run(cmd, shell=True, check=True)
        print(f'Screenshot saved to {output_file}')
        return output_file

    def list_screenshots(self):
        """Return the sorted names of all PNG screenshots in the output directory."""
        return sorted(
            filename
            for filename in os.listdir(self.output_dir)
            if filename.endswith('.png')
        )

    def cleanup_screenshots(self, older_than_days=30):
        """Delete every screenshot older than *older_than_days* days."""
        cutoff = (
            datetime.now().timestamp()
            - timedelta(days=older_than_days).total_seconds()
        )
        for filename in os.listdir(self.output_dir):
            filepath = os.path.join(self.output_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old screenshot: {filename}')


def print_menu():
    """Print the main menu of the interactive interface."""
    print('\nWebsite Screenshot Tool:')
    print('1. Capture website screenshot')
    print('2. List available screenshots')
    print('3. Cleanup old screenshots')
    print('4. Exit')
    print('Supported browsers: chrome, firefox, webkit')


def main():
    """Run the interactive screenshot tool."""
    screenshot_tool = WebsiteScreenshot()

    while True:
        print_menu()
        choice = input('Enter your choice: ')

        if choice == '1':
            url = input('Website URL: ')
            browser = input('Browser (chrome/firefox/webkit): ') or 'chrome'
            delay = input('Delay in seconds (default 2): ') or '2'
            full_page = input('Full page (y/n): ').lower() == 'y'
            try:
                screenshot_tool.capture_website(url, browser, int(delay), full_page)
            except Exception as e:
                print(f'Error: {e}')
        elif choice == '2':
            screenshots = screenshot_tool.list_screenshots()
            print('Available screenshots:')
            for shot in screenshots:
                print(f'- {shot}')
        elif choice == '3':
            days = input('Delete screenshots older than (days): ') or '30'
            screenshot_tool.cleanup_screenshots(int(days))
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
