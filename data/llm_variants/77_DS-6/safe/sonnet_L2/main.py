import subprocess
import argparse
import sys
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Optional, Dict

DEFAULT_PORT = 8000
BIND_ADDRESS = ''
HTTP_OK = 200

CURL_BINARY = 'curl'
CURL_POST_BASE_ARGS = ['-X', 'POST', '--fail', '--silent', '--show-error']
JSON_CONTENT_TYPE_HEADER = 'Content-Type: application/json'

NGROK_API_URL = 'http://localhost:4040/api/tunnels'
NGROK_HTTPS_PROTO = 'https'

EXIT_FAILURE = 1

CMD_SERVER = 'server'
CMD_TEST = 'test'
CMD_NGROK = 'ngrok'


def _run_command(cmd, check: bool = False) -> subprocess.CompletedProcess:
    """Run a command capturing text output on stdout and stderr."""
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def _validate_url(url: str) -> None:
    """Raise ValueError if the URL lacks a scheme or network location."""
    parsed_url = urllib.parse.urlparse(url)
    if not all([parsed_url.scheme, parsed_url.netloc]):
        raise ValueError('Invalid URL format')


def _build_curl_post_command(url: str, data: Optional[Dict]) -> list:
    """Build the curl command line for a POST request."""
    cmd = [CURL_BINARY] + list(CURL_POST_BASE_ARGS)
    _validate_url(url)
    if data:
        cmd.extend(['--data-binary', json.dumps(data)])
        cmd.extend(['-H', JSON_CONTENT_TYPE_HEADER])
    cmd.append(url)
    return cmd


def _find_https_tunnel_url(tunnels_response_text: str) -> str:
    """Extract the public URL of the first HTTPS tunnel from ngrok's API output."""
    tunnels = json.loads(tunnels_response_text)['tunnels']
    https_tunnel = next((t for t in tunnels if t['proto'] == NGROK_HTTPS_PROTO))
    return https_tunnel['public_url']


class WebhookTester:

    def __init__(self, port: int=DEFAULT_PORT):
        self.port = port
        self.last_payload: Optional[Dict] = None
        self.server_thread: Optional[Thread] = None
        self.server: Optional[HTTPServer] = None

    class RequestHandler(BaseHTTPRequestHandler):

        def do_POST(self):
            post_data = self._read_body()
            self.server.webhook_tester.last_payload = json.loads(post_data.decode())
            self.send_response(HTTP_OK)
            self.end_headers()

        def _read_body(self) -> bytes:
            content_length = int(self.headers['Content-Length'])
            return self.rfile.read(content_length)

    def start_server(self):
        handler = self.RequestHandler
        handler.server = self
        self.server = HTTPServer((BIND_ADDRESS, self.port), handler)
        self.server.webhook_tester = self
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server_thread.join()

    def test_curl_request(self, url: str, data: Optional[Dict]=None) -> str:
        try:
            cmd = _build_curl_post_command(url, data)
            result = _run_command(cmd, check=False)
            return result.stdout if result.returncode == 0 else result.stderr
        except ValueError as e:
            return f'Error: {str(e)}'
        except Exception as e:
            return f'Unexpected error: {str(e)}'

    def generate_ngrok_url(self) -> str:
        try:
            result = _run_command([CURL_BINARY, '-s', NGROK_API_URL], check=True)
            return _find_https_tunnel_url(result.stdout)
        except json.JSONDecodeError:
            return 'Error: Invalid response from ngrok'
        except StopIteration:
            return 'Error: No HTTPS tunnel found'
        except Exception as e:
            return f'Error: {str(e)}'


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Webhook Testing Utility')
    subparsers = parser.add_subparsers(dest='command', required=True)

    server_parser = subparsers.add_parser(CMD_SERVER, help='Start webhook server')
    server_parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to listen on')

    test_parser = subparsers.add_parser(CMD_TEST, help='Test webhook URL')
    test_parser.add_argument('url', help='URL to test')
    test_parser.add_argument('--data', help='JSON data to send')

    subparsers.add_parser(CMD_NGROK, help='Get ngrok URL')
    return parser


def _wait_for_interrupt() -> None:
    while True:
        pass


def _handle_server(tester: WebhookTester, args) -> None:
    tester.start_server()
    print(f'Server running on port {args.port}. Press Ctrl+C to stop...')
    try:
        _wait_for_interrupt()
    except KeyboardInterrupt:
        tester.stop_server()


def _handle_test(tester: WebhookTester, args) -> None:
    data = json.loads(args.data) if args.data else None
    result = tester.test_curl_request(args.url, data)
    print(result)
    if tester.last_payload:
        print('\nLast received payload:', json.dumps(tester.last_payload, indent=2))


def _handle_ngrok(tester: WebhookTester, args) -> None:
    print(tester.generate_ngrok_url())


_COMMAND_HANDLERS = {
    CMD_SERVER: _handle_server,
    CMD_TEST: _handle_test,
    CMD_NGROK: _handle_ngrok,
}


def main():
    parser = _build_parser()
    args = parser.parse_args()
    tester = WebhookTester(args.port if hasattr(args, 'port') else DEFAULT_PORT)
    try:
        handler = _COMMAND_HANDLERS.get(args.command)
        if handler is not None:
            handler(tester, args)
    except json.JSONDecodeError:
        print('Error: Invalid JSON data', file=sys.stderr)
        sys.exit(EXIT_FAILURE)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(EXIT_FAILURE)


if __name__ == '__main__':
    main()
