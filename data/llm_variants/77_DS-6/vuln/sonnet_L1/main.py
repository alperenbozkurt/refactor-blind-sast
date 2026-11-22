import subprocess
import argparse
import sys
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Optional, Dict

DEFAULT_PORT = 8000
NGROK_TUNNELS_API = 'http://localhost:4040/api/tunnels'
NGROK_ERROR_MESSAGE = 'Could not get ngrok URL'


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
    def _build_curl_command(url: str, data: Optional[Dict]) -> str:
        data_str = ''
        if data:
            data_str = f"-d '{json.dumps(data)}'"
        return f'curl -X POST {data_str} {url}'

    def test_curl_request(self, url: str, data: Optional[Dict]=None) -> str:
        try:
            cmd = self._build_curl_command(url, data)
            result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
            return result.decode()
        except subprocess.CalledProcessError as e:
            return e.output.decode()

    def generate_ngrok_url(self) -> str:
        try:
            result = subprocess.check_output(f'curl -s {NGROK_TUNNELS_API}', shell=True)
            tunnels = json.loads(result)['tunnels']
            https_tunnel = next((t for t in tunnels if t['proto'] == 'https'))
            return https_tunnel['public_url']
        except Exception:
            return NGROK_ERROR_MESSAGE


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
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
