import subprocess
import argparse
import sys
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Optional, Dict

DEFAULT_PORT = 8000
NGROK_TUNNELS_URL = 'http://localhost:4040/api/tunnels'


class WebhookTester:

    def __init__(self, port: int=DEFAULT_PORT):
        self.port = port
        self.last_payload: Optional[Dict] = None
        self.server_thread: Optional[Thread] = None
        self.server: Optional[HTTPServer] = None

    class RequestHandler(BaseHTTPRequestHandler):

        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            self.server.webhook_tester.last_payload = json.loads(post_data.decode())
            self.send_response(200)
            self.end_headers()

    def start_server(self):
        handler = self.RequestHandler
        handler.server = self
        self.server = HTTPServer(('', self.port), handler)
        self.server.webhook_tester = self
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server_thread.join()

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed_url = urllib.parse.urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise ValueError('Invalid URL format')

    @staticmethod
    def _run_command(cmd, check: bool) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=check,
        )

    def test_curl_request(self, url: str, data: Optional[Dict]=None) -> str:
        try:
            cmd = ['curl', '-X', 'POST', '--fail', '--silent', '--show-error']
            self._validate_url(url)
            if data:
                cmd.extend(['--data-binary', json.dumps(data)])
                cmd.extend(['-H', 'Content-Type: application/json'])
            cmd.append(url)
            result = self._run_command(cmd, check=False)
            return result.stdout if result.returncode == 0 else result.stderr
        except ValueError as e:
            return f'Error: {str(e)}'
        except Exception as e:
            return f'Unexpected error: {str(e)}'

    def generate_ngrok_url(self) -> str:
        try:
            result = self._run_command(['curl', '-s', NGROK_TUNNELS_URL], check=True)
            tunnels = json.loads(result.stdout)['tunnels']
            https_tunnel = next((t for t in tunnels if t['proto'] == 'https'))
            return https_tunnel['public_url']
        except json.JSONDecodeError:
            return 'Error: Invalid response from ngrok'
        except StopIteration:
            return 'Error: No HTTPS tunnel found'
        except Exception as e:
            return f'Error: {str(e)}'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Webhook Testing Utility')
    subparsers = parser.add_subparsers(dest='command', required=True)

    server_parser = subparsers.add_parser('server', help='Start webhook server')
    server_parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to listen on')

    test_parser = subparsers.add_parser('test', help='Test webhook URL')
    test_parser.add_argument('url', help='URL to test')
    test_parser.add_argument('--data', help='JSON data to send')

    subparsers.add_parser('ngrok', help='Get ngrok URL')
    return parser


def run_server_command(tester: WebhookTester, args) -> None:
    tester.start_server()
    print(f'Server running on port {args.port}. Press Ctrl+C to stop...')
    try:
        while True:
            pass
    except KeyboardInterrupt:
        tester.stop_server()


def run_test_command(tester: WebhookTester, args) -> None:
    data = json.loads(args.data) if args.data else None
    result = tester.test_curl_request(args.url, data)
    print(result)
    if tester.last_payload:
        print('\nLast received payload:', json.dumps(tester.last_payload, indent=2))


def run_ngrok_command(tester: WebhookTester, args) -> None:
    print(tester.generate_ngrok_url())


COMMAND_HANDLERS = {
    'server': run_server_command,
    'test': run_test_command,
    'ngrok': run_ngrok_command,
}


def main():
    args = build_parser().parse_args()
    tester = WebhookTester(args.port if hasattr(args, 'port') else DEFAULT_PORT)
    try:
        COMMAND_HANDLERS[args.command](tester, args)
    except json.JSONDecodeError:
        print('Error: Invalid JSON data', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
