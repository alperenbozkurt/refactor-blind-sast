"""Webhook testing utility.

Provides a small HTTP server that records the most recent JSON payload it
receives, a helper for sending test POST requests via ``curl``, and a helper
for discovering the public URL of a locally running ngrok agent.
"""

import argparse
import json
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Dict, Optional

# Server defaults.
DEFAULT_PORT = 8000
HTTP_STATUS_OK = 200
CONTENT_LENGTH_HEADER = 'Content-Length'

# ngrok inspection API.
NGROK_API_URL = 'http://localhost:4040/api/tunnels'
NGROK_HTTPS_PROTOCOL = 'https'
NGROK_URL_ERROR_MESSAGE = 'Could not get ngrok URL'

# CLI command names.
SERVER_COMMAND = 'server'
TEST_COMMAND = 'test'
NGROK_COMMAND = 'ngrok'


class WebhookTester:
    """Run a webhook-receiving server and exercise webhook endpoints."""

    def __init__(self, port: int = 8000):
        self.port = port
        self.last_payload: Optional[Dict] = None
        self.server_thread: Optional[Thread] = None
        self.server: Optional[HTTPServer] = None

    class RequestHandler(BaseHTTPRequestHandler):
        """Handle incoming webhook POST requests."""

        def do_POST(self):
            self.server.webhook_tester.last_payload = self._read_json_payload()
            self._send_ok_response()

        def _read_json_payload(self) -> Dict:
            content_length = int(self.headers[CONTENT_LENGTH_HEADER])
            post_data = self.rfile.read(content_length)
            return json.loads(post_data.decode())

        def _send_ok_response(self) -> None:
            self.send_response(HTTP_STATUS_OK)
            self.end_headers()

    def start_server(self):
        handler = self.RequestHandler
        handler.server = self
        self.server = self._create_server(handler)
        self.server_thread = self._create_server_thread()
        self.server_thread.start()

    def _create_server(self, handler: type) -> HTTPServer:
        server = HTTPServer(('', self.port), handler)
        server.webhook_tester = self
        return server

    def _create_server_thread(self) -> Thread:
        thread = Thread(target=self.server.serve_forever)
        thread.daemon = True
        return thread

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server_thread.join()

    def test_curl_request(self, url: str, data: Optional[Dict] = None) -> str:
        try:
            cmd = self._build_curl_command(url, data)
            result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
            return result.decode()
        except subprocess.CalledProcessError as e:
            return e.output.decode()

    @staticmethod
    def _build_curl_command(url: str, data: Optional[Dict]) -> str:
        data_str = ''
        if data:
            data_str = f"-d '{json.dumps(data)}'"
        return f'curl -X POST {data_str} {url}'

    def generate_ngrok_url(self) -> str:
        try:
            tunnels = self._fetch_ngrok_tunnels()
            https_tunnel = next(t for t in tunnels if t['proto'] == NGROK_HTTPS_PROTOCOL)
            return https_tunnel['public_url']
        except Exception:
            return NGROK_URL_ERROR_MESSAGE

    @staticmethod
    def _fetch_ngrok_tunnels() -> list:
        result = subprocess.check_output(f'curl -s {NGROK_API_URL}', shell=True)
        return json.loads(result)['tunnels']


def build_argument_parser() -> argparse.ArgumentParser:
    """Construct the command-line argument parser."""
    parser = argparse.ArgumentParser(description='Webhook Testing Utility')
    subparsers = parser.add_subparsers(dest='command', required=True)

    server_parser = subparsers.add_parser(SERVER_COMMAND, help='Start webhook server')
    server_parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to listen on')

    test_parser = subparsers.add_parser(TEST_COMMAND, help='Test webhook URL')
    test_parser.add_argument('url', help='URL to test')
    test_parser.add_argument('--data', help='JSON data to send')

    subparsers.add_parser(NGROK_COMMAND, help='Get ngrok URL')

    return parser


def run_server_command(tester: WebhookTester, port: int) -> None:
    tester.start_server()
    print(f'Server running on port {port}. Press Ctrl+C to stop...')
    try:
        while True:
            pass
    except KeyboardInterrupt:
        tester.stop_server()


def run_test_command(tester: WebhookTester, url: str, data_arg: Optional[str]) -> None:
    data = json.loads(data_arg) if data_arg else None
    result = tester.test_curl_request(url, data)
    print(result)
    if tester.last_payload:
        print('\nLast received payload:', json.dumps(tester.last_payload, indent=2))


def run_ngrok_command(tester: WebhookTester) -> None:
    print(tester.generate_ngrok_url())


def main():
    parser = build_argument_parser()
    args = parser.parse_args()
    tester = WebhookTester(args.port if hasattr(args, 'port') else DEFAULT_PORT)
    command_handlers = {
        SERVER_COMMAND: lambda: run_server_command(tester, args.port),
        TEST_COMMAND: lambda: run_test_command(tester, args.url, args.data),
        NGROK_COMMAND: lambda: run_ngrok_command(tester),
    }
    try:
        command_handlers[args.command]()
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
