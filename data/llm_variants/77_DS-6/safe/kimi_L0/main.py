import argparse
import json
import subprocess
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Dict, Optional

NGROK_API_URL = 'http://localhost:4040/api/tunnels'


class WebhookTester:
    """Utility for testing webhooks locally and through ngrok."""

    def __init__(self, port: int = 8000):
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
        self.server = HTTPServer(('', self.port), self.RequestHandler)
        self.server.webhook_tester = self
        self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server_thread.join()

    def test_curl_request(self, url: str, data: Optional[Dict] = None) -> str:
        try:
            parsed_url = urllib.parse.urlparse(url)
            if not (parsed_url.scheme and parsed_url.netloc):
                raise ValueError('Invalid URL format')
            cmd = ['curl', '-X', 'POST', '--fail', '--silent', '--show-error']
            if data:
                cmd += ['--data-binary', json.dumps(data),
                        '-H', 'Content-Type: application/json']
            cmd.append(url)
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return result.stdout if result.returncode == 0 else result.stderr
        except ValueError as e:
            return f'Error: {e}'
        except Exception as e:
            return f'Unexpected error: {e}'

    def generate_ngrok_url(self) -> str:
        try:
            result = subprocess.run(
                ['curl', '-s', NGROK_API_URL],
                capture_output=True,
                text=True,
                check=True,
            )
            tunnels = json.loads(result.stdout)['tunnels']
            https_tunnel = next(t for t in tunnels if t['proto'] == 'https')
            return https_tunnel['public_url']
        except json.JSONDecodeError:
            return 'Error: Invalid response from ngrok'
        except StopIteration:
            return 'Error: No HTTPS tunnel found'
        except Exception as e:
            return f'Error: {e}'


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Webhook Testing Utility')
    subparsers = parser.add_subparsers(dest='command', required=True)

    server_parser = subparsers.add_parser('server', help='Start webhook server')
    server_parser.add_argument('--port', type=int, default=8000,
                               help='Port to listen on')

    test_parser = subparsers.add_parser('test', help='Test webhook URL')
    test_parser.add_argument('url', help='URL to test')
    test_parser.add_argument('--data', help='JSON data to send')

    subparsers.add_parser('ngrok', help='Get ngrok URL')
    return parser


def main():
    args = _create_parser().parse_args()
    tester = WebhookTester(getattr(args, 'port', 8000))
    try:
        if args.command == 'server':
            tester.start_server()
            print(f'Server running on port {args.port}. Press Ctrl+C to stop...')
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                tester.stop_server()
        elif args.command == 'test':
            data = json.loads(args.data) if args.data else None
            result = tester.test_curl_request(args.url, data)
            print(result)
            if tester.last_payload:
                print('\nLast received payload:',
                      json.dumps(tester.last_payload, indent=2))
        elif args.command == 'ngrok':
            print(tester.generate_ngrok_url())
    except json.JSONDecodeError:
        print('Error: Invalid JSON data', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
