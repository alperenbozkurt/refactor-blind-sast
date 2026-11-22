import os
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse


class WebsiteScreenshot:
    """Capture website screenshots using chrome, firefox, or webkit backends."""

    def __init__(self, output_dir='screenshots'):
        self.output_dir = output_dir
        self.supported_browsers = ['chrome', 'firefox', 'webkit']
        self.create_output_dir()

    def create_output_dir(self):
        """Create the output directory if it does not already exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def validate_url(self, url):
        """Return True when ``url`` has both a scheme and a network location."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    def generate_filename(self, url):
        """Build a timestamped PNG filename based on the URL's domain."""
        domain = urlparse(url).netloc
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{domain}_{timestamp}.png'

    def capture_website(self, url, browser='chrome', delay=2, full_page=False):
        """Capture a screenshot of ``url`` and return the output file path."""
        if not self.validate_url(url):
            raise ValueError('Invalid URL provided')
        output_file = os.path.join(self.output_dir, self.generate_filename(url))
        try:
            self._run_capture(browser, url, output_file, delay, full_page)
            print(f'Screenshot saved to {output_file}')
            return output_file
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode().strip() if e.stderr else str(e)
            raise RuntimeError(f'Screenshot failed: {error_msg}')
        except Exception as e:
            raise RuntimeError(f'Error during screenshot capture: {str(e)}')

    def _run_capture(self, browser, url, output_file, delay, full_page):
        """Dispatch to the capture command for the selected browser."""
        if browser == 'chrome':
            self._capture_with_chrome(url, output_file, delay, full_page)
        elif browser == 'firefox':
            self._capture_with_firefox(url, output_file, delay)
        else:
            self._capture_with_webkit(url, output_file)

    def _capture_with_chrome(self, url, output_file, delay, full_page):
        args = ['wkhtmltoimage', '--delay', str(delay)]
        if full_page:
            args.append('--enable-javascript')
        args.extend([url, output_file])
        subprocess.run(args, check=True, stderr=subprocess.PIPE)

    def _capture_with_firefox(self, url, output_file, delay):
        args = [
            'cutycapt',
            f'--url={url}',
            f'--out={output_file}',
            f'--delay={delay}',
        ]
        subprocess.run(args, check=True, stderr=subprocess.PIPE)

    def _capture_with_webkit(self, url, output_file):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        rasterize_script = os.path.join(script_dir, 'rasterize.js')
        if not os.path.exists(rasterize_script):
            raise FileNotFoundError('rasterize.js script not found')
        subprocess.run(
            ['phantomjs', rasterize_script, url, output_file],
            check=True,
            stderr=subprocess.PIPE,
        )

    def list_screenshots(self):
        """Return a sorted list of PNG screenshots in the output directory."""
        return sorted(
            filename
            for filename in os.listdir(self.output_dir)
            if filename.endswith('.png')
        )

    def cleanup_screenshots(self, older_than_days=30):
        """Delete screenshots older than the given number of days."""
        seconds_per_day = 86400
        cutoff = datetime.now().timestamp() - older_than_days * seconds_per_day
        for filename in os.listdir(self.output_dir):
            filepath = os.path.join(self.output_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f'Removed old screenshot: {filename}')


def print_menu():
    """Display the main menu."""
    print('\nWebsite Screenshot Tool:')
    print('1. Capture website screenshot')
    print('2. List available screenshots')
    print('3. Cleanup old screenshots')
    print('4. Exit')
    print('Supported browsers: chrome, firefox, webkit')


def main():
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
