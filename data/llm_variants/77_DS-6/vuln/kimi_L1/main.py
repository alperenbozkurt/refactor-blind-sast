"""Utility for testing webhooks locally and inspecting ngrok tunnels."""

import argparse
import json
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Dict, Optional

DEFAULT_PORT = 8000
NGROK_TUNNELS_URL = 'http://localhost:4040/api/tunnels'
NGROK_UNAVAILABLE_MESSAGE = 'Could not get ngrok URL'


class WebhookTester:
    """Receive webhook POST requests locally and send test requests via curl."""

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.last_payload: Optional[Dict] = None
        self.server_thread: Optional[Thread] = None
        self.server: Optional[HTTPServer] = None

    class RequestHandler(BaseHTTPRequestHandler):
        """Store the JSON body of each incoming POST request on the tester."""

        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            self.server.webhook_tester.last_payload = json.loads(post_data.decode())
            self.send_response(200)
            self.end_headers()

    def start_server(self):
        """Start the HTTP server on a background daemon thread."""
        handler = self.RequestHandler
        # Give the handler a reference back to this tester instance.
        handler.server = self
        self.server = HTTPServer(('', self.port), handler)
        self.server.webhook_tester = self
        self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def stop_server(self):
        """Shut the server down and wait for its thread to finish."""
        if self.server is not None:
            self.server.shutdown()
            self.server_thread.join()

    def test_curl_request(self, url: str, data: Optional[Dict] = None) -> str:
        """POST ``data`` to ``url`` with curl and return curl's output."""
        try:
            data_str = ''
            if data:
                data_str = f"-d '{json.dumps(data)}'"
            cmd = f'curl -X POST {data_str} {url}'
            result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
            return result.decode()
        except subprocess.CalledProcessError as e:
            return e.output.decode()

    def generate_ngrok_url(self) -> str:
        """Return the public HTTPS URL of the running ngrok tunnel."""
        try:
            result = subprocess.check_output(f'curl -s {NGROK_TUNNELS_URL}', shell=True)
            tunnels = json.loads(result)['tunnels']
            https_tunnel = next(t for t in tunnels if t['proto'] == 'https')
            return https_tunnel['public_url']
        except Exception:
            return NGROK_UNAVAILABLE_MESSAGE


def _build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser (commands: server, test, ngrok)."""
    parser = argparse.ArgumentParser(description='Webhook Testing Utility')
    subparsers = parser.add_subparsers(dest='command', required=True)

    server_parser = subparsers.add_parser('server', help='Start webhook server')
    server_parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to listen on')

    test_parser = subparsers.add_parser('test', help='Test webhook URL')
    test_parser.add_argument('url', help='URL to test')
    test_parser.add_argument('--data', help='JSON data to send')

    subparsers.add_parser('ngrok', help='Get ngrok URL')
    return parser


def _run_server(tester: WebhookTester, port: int) -> None:
    """Start the webhook server and block until interrupted."""
    tester.start_server()
    print(f'Server running on port {port}. Press Ctrl+C to stop...')
    try:
        while True:
            pass
    except KeyboardInterrupt:
        tester.stop_server()


def _run_test(tester: WebhookTester, url: str, raw_data: Optional[str]) -> None:
    """Send a test POST to ``url`` and print the last received payload."""
    data = json.loads(raw_data) if raw_data else None
    result = tester.test_curl_request(url, data)
    print(result)
    if tester.last_payload:
        print('\nLast received payload:', json.dumps(tester.last_payload, indent=2))


def main():
    parser = _build_parser()
    args = parser.parse_args()

    tester = WebhookTester(args.port if hasattr(args, 'port') else DEFAULT_PORT)
    try:
        if args.command == 'server':
            _run_server(tester, args.port)
        elif args.command == 'test':
            _run_test(tester, args.url, args.data)
        elif args.command == 'ngrok':
            print(tester.generate_ngrok_url())
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
