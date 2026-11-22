import subprocess
import argparse
import sys
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Optional, Dict

DEFAULT_PORT = 8000
DEFAULT_BIND_HOST = ''
HTTP_OK = 200
CONTENT_LENGTH_HEADER = 'Content-Length'
NGROK_TUNNELS_URL = 'http://localhost:4040/api/tunnels'
NGROK_TUNNELS_COMMAND = f'curl -s {NGROK_TUNNELS_URL}'
NGROK_PROTOCOL = 'https'
NGROK_ERROR_MESSAGE = 'Could not get ngrok URL'
PAYLOAD_JSON_INDENT = 2

COMMAND_SERVER = 'server'
COMMAND_TEST = 'test'
COMMAND_NGROK = 'ngrok'


def _build_curl_command(url: str, data: Optional[Dict] = None) -> str:
    """Build the shell command used to POST to ``url``."""
    data_str = ''
    if data:
        data_str = f"-d '{json.dumps(data)}'"
    return f'curl -X POST {data_str} {url}'


def _run_shell(cmd: str, **kwargs) -> bytes:
    """Run a shell command and return its output."""
    return subprocess.check_output(cmd, shell=True, **kwargs)


class WebhookTester:

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.last_payload: Optional[Dict] = None
        self.server_thread: Optional[Thread] = None
        self.server: Optional[HTTPServer] = None

    class RequestHandler(BaseHTTPRequestHandler):

        def _read_json_body(self):
            content_length = int(self.headers[CONTENT_LENGTH_HEADER])
            post_data = self.rfile.read(content_length)
            return json.loads(post_data.decode())

        def do_POST(self):
            self.server.webhook_tester.last_payload = self._read_json_body()
            self.send_response(HTTP_OK)
            self.end_headers()

    def start_server(self):
        handler = self.RequestHandler
        handler.server = self
        self.server = HTTPServer((DEFAULT_BIND_HOST, self.port), handler)
        self.server.webhook_tester = self
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server_thread.join()

    def test_curl_request(self, url: str, data: Optional[Dict] = None) -> str:
        try:
            cmd = _build_curl_command(url, data)
            result = _run_shell(cmd, stderr=subprocess.STDOUT)
            return result.decode()
        except subprocess.CalledProcessError as e:
            return e.output.decode()

    def generate_ngrok_url(self) -> str:
        try:
            result = _run_shell(NGROK_TUNNELS_COMMAND)
            tunnels = json.loads(result)['tunnels']
            https_tunnel = next((t for t in tunnels if t['proto'] == NGROK_PROTOCOL))
            return https_tunnel['public_url']
        except Exception:
            return NGROK_ERROR_MESSAGE


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Webhook Testing Utility')
    subparsers = parser.add_subparsers(dest='command', required=True)

    server_parser = subparsers.add_parser(COMMAND_SERVER, help='Start webhook server')
    server_parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to listen on')

    test_parser = subparsers.add_parser(COMMAND_TEST, help='Test webhook URL')
    test_parser.add_argument('url', help='URL to test')
    test_parser.add_argument('--data', help='JSON data to send')

    subparsers.add_parser(COMMAND_NGROK, help='Get ngrok URL')
    return parser


def _run_server_command(tester: WebhookTester, args) -> None:
    tester.start_server()
    print(f'Server running on port {args.port}. Press Ctrl+C to stop...')
    try:
        while True:
            pass
    except KeyboardInterrupt:
        tester.stop_server()


def _run_test_command(tester: WebhookTester, args) -> None:
    data = json.loads(args.data) if args.data else None
    result = tester.test_curl_request(args.url, data)
    print(result)
    if tester.last_payload:
        print('\nLast received payload:',
              json.dumps(tester.last_payload, indent=PAYLOAD_JSON_INDENT))


def _run_ngrok_command(tester: WebhookTester, args) -> None:
    print(tester.generate_ngrok_url())


_COMMAND_HANDLERS = {
    COMMAND_SERVER: _run_server_command,
    COMMAND_TEST: _run_test_command,
    COMMAND_NGROK: _run_ngrok_command,
}


def main():
    parser = _build_parser()
    args = parser.parse_args()
    tester = WebhookTester(args.port if hasattr(args, 'port') else DEFAULT_PORT)
    try:
        handler = _COMMAND_HANDLERS.get(args.command)
        if handler is not None:
            handler(tester, args)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
