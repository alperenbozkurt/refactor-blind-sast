import os
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse

SECONDS_PER_DAY = 86400


class WebsiteScreenshot:
    """Capture website screenshots using external command-line tools."""

    def __init__(self, output_dir='screenshots'):
        self.output_dir = output_dir
        self.supported_browsers = ['chrome', 'firefox', 'webkit']
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not already exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_url(self, url):
        """Return True if the URL has both a scheme and a network location."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def generate_filename(self, url):
        """Build a timestamped PNG filename based on the URL's domain."""
        domain = urlparse(url).netloc
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{domain}_{timestamp}.png'

    def capture_website(self, url, browser='chrome', delay=2, full_page=False):
        """Capture a screenshot of the given URL and return the file path."""
        if not self.validate_url(url):
            raise ValueError('Invalid URL provided')
        output_file = os.path.join(self.output_dir, self.generate_filename(url))
        try:
            if browser == 'chrome':
                self._capture_with_chrome(url, output_file, delay, full_page)
            elif browser == 'firefox':
                self._capture_with_firefox(url, output_file, delay)
            else:
                self._capture_with_webkit(url, output_file)
            print(f'Screenshot saved to {output_file}')
            return output_file
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode().strip() if e.stderr else str(e)
            raise RuntimeError(f'Screenshot failed: {error_msg}')
        except Exception as e:
            raise RuntimeError(f'Error during screenshot capture: {str(e)}')

    def _capture_with_chrome(self, url, output_file, delay, full_page):
        args = ['wkhtmltoimage', '--delay', str(delay)]
        if full_page:
            args.append('--enable-javascript')
        args.extend([url, output_file])
        self._run_command(args)

    def _capture_with_firefox(self, url, output_file, delay):
        self._run_command([
            'cutycapt',
            f'--url={url}',
            f'--out={output_file}',
            f'--delay={delay}',
        ])

    def _capture_with_webkit(self, url, output_file):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        rasterize_script = os.path.join(script_dir, 'rasterize.js')
        if not os.path.exists(rasterize_script):
            raise FileNotFoundError('rasterize.js script not found')
        self._run_command(['phantomjs', rasterize_script, url, output_file])

    @staticmethod
    def _run_command(args):
        subprocess.run(args, check=True, stderr=subprocess.PIPE)

    def list_screenshots(self):
        """Return a sorted list of PNG screenshots in the output directory."""
        return sorted(
            f for f in os.listdir(self.output_dir) if f.endswith('.png')
        )

    def cleanup_screenshots(self, older_than_days=30):
        """Remove files in the output directory older than the given age."""
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
    browser = input('Browser (chrome/firefox/webkit): ') or 'chrome'
    delay = input('Delay in seconds (default 2): ') or '2'
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
    days = input('Delete screenshots older than (days): ') or '30'
    screenshot_tool.cleanup_screenshots(int(days))


def main():
    screenshot_tool = WebsiteScreenshot()
    while True:
        print_menu()
        choice = input('Enter your choice: ')
        if choice == '1':
            _handle_capture(screenshot_tool)
        elif choice == '2':
            _handle_list(screenshot_tool)
        elif choice == '3':
            _handle_cleanup(screenshot_tool)
        elif choice == '4':
            print('Exiting...')
            break
        else:
            print('Invalid choice. Please try again.')


if __name__ == '__main__':
    main()
