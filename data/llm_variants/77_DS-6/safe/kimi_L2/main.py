"""Webhook testing utility.

Spins up a small HTTP server that records the last JSON payload it
receives, provides a curl based client for exercising webhook endpoints,
and can retrieve the public HTTPS URL of a running ngrok tunnel.
"""

import argparse
import json
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8000
BIND_ADDRESS = ''
HTTP_OK = 200

NGROK_API_URL = 'http://localhost:4040/api/tunnels'
NGROK_PROTO_HTTPS = 'https'

CURL_POST_BASE = ('curl', '-X', 'POST', '--fail', '--silent', '--show-error')
CURL_SILENT_FLAG = '-s'
CURL_DATA_BINARY_FLAG = '--data-binary'
CURL_HEADER_FLAG = '-H'
JSON_CONTENT_TYPE = 'Content-Type: application/json'

ERROR_INVALID_URL = 'Invalid URL format'
ERROR_INVALID_NGROK_RESPONSE = 'Error: Invalid response from ngrok'
ERROR_NO_HTTPS_TUNNEL = 'Error: No HTTPS tunnel found'
ERROR_INVALID_JSON_DATA = 'Error: Invalid JSON data'

CLI_DESCRIPTION = 'Webhook Testing Utility'
SERVER_RUNNING_MESSAGE = 'Server running on port {port}. Press Ctrl+C to stop...'
LAST_PAYLOAD_HEADING = '\nLast received payload:'


@dataclass(frozen=True)
class WebhookTesterConfig:
    """Immutable settings used by :class:`WebhookTester`."""

    port: int = DEFAULT_PORT
    bind_address: str = BIND_ADDRESS
    ngrok_api_url: str = NGROK_API_URL


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _run_process(command: List[str], check: bool = False) -> subprocess.CompletedProcess:
    """Execute *command*, capturing stdout and stderr as text."""
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def _validate_url(url: str) -> None:
    """Raise ``ValueError`` if *url* is missing a scheme or network location."""
    parsed_url = urllib.parse.urlparse(url)
    if not all([parsed_url.scheme, parsed_url.netloc]):
        raise ValueError(ERROR_INVALID_URL)


def _build_curl_command(url: str, data: Optional[Dict] = None) -> List[str]:
    """Assemble the curl invocation used to POST an optional JSON body to *url*."""
    cmd = list(CURL_POST_BASE)
    _validate_url(url)
    if data:
        cmd.extend([CURL_DATA_BINARY_FLAG, json.dumps(data)])
        cmd.extend([CURL_HEADER_FLAG, JSON_CONTENT_TYPE])
    cmd.append(url)
    return cmd


def _extract_https_tunnel_url(api_response: str) -> str:
    """Return the public HTTPS tunnel URL from the ngrok API response body."""
    tunnels = json.loads(api_response)['tunnels']
    https_tunnel = next((t for t in tunnels if t['proto'] == NGROK_PROTO_HTTPS))
    return https_tunnel['public_url']


# ---------------------------------------------------------------------------
# Webhook tester
# ---------------------------------------------------------------------------

class WebhookTester:
    """Receive webhooks locally and test remote webhook endpoints via curl."""

    def __init__(self, port: int = DEFAULT_PORT):
        self.config = WebhookTesterConfig(port=port)
        self.port = self.config.port
        self.last_payload: Optional[Dict] = None
        self.server_thread: Optional[Thread] = None
        self.server: Optional[HTTPServer] = None

    class RequestHandler(BaseHTTPRequestHandler):
        """Store the decoded JSON body of every incoming POST request."""

        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            self.server.webhook_tester.last_payload = json.loads(post_data.decode())
            self.send_response(HTTP_OK)
            self.end_headers()

    def start_server(self):
        handler = self.RequestHandler
        handler.server = self
        self.server = HTTPServer((self.config.bind_address, self.port), handler)
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
            result = _run_process(cmd)
            return result.stdout if result.returncode == 0 else result.stderr
        except ValueError as e:
            return f'Error: {str(e)}'
        except Exception as e:
            return f'Unexpected error: {str(e)}'

    def generate_ngrok_url(self) -> str:
        try:
            command = ['curl', CURL_SILENT_FLAG, self.config.ngrok_api_url]
            result = _run_process(command, check=True)
            return _extract_https_tunnel_url(result.stdout)
        except json.JSONDecodeError:
            return ERROR_INVALID_NGROK_RESPONSE
        except StopIteration:
            return ERROR_NO_HTTPS_TUNNEL
        except Exception as e:
            return f'Error: {str(e)}'


# ---------------------------------------------------------------------------
# Command line interface
# ---------------------------------------------------------------------------

def _build_argument_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the webhook testing utility."""
    parser = argparse.ArgumentParser(description=CLI_DESCRIPTION)
    subparsers = parser.add_subparsers(dest='command', required=True)

    server_parser = subparsers.add_parser('server', help='Start webhook server')
    server_parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to listen on')

    test_parser = subparsers.add_parser('test', help='Test webhook URL')
    test_parser.add_argument('url', help='URL to test')
    test_parser.add_argument('--data', help='JSON data to send')

    subparsers.add_parser('ngrok', help='Get ngrok URL')
    return parser


def _run_server_command(tester: WebhookTester, args: argparse.Namespace) -> None:
    """Start the webhook server and block until interrupted."""
    tester.start_server()
    print(SERVER_RUNNING_MESSAGE.format(port=args.port))
    try:
        while True:
            pass
    except KeyboardInterrupt:
        tester.stop_server()


def _run_test_command(tester: WebhookTester, args: argparse.Namespace) -> None:
    """Send a test request to a webhook URL and show the result."""
    data = json.loads(args.data) if args.data else None
    result = tester.test_curl_request(args.url, data)
    print(result)
    if tester.last_payload:
        print(LAST_PAYLOAD_HEADING, json.dumps(tester.last_payload, indent=2))


def _run_ngrok_command(tester: WebhookTester, args: argparse.Namespace) -> None:
    """Print the public HTTPS URL of the running ngrok tunnel."""
    print(tester.generate_ngrok_url())


_COMMAND_HANDLERS = {
    'server': _run_server_command,
    'test': _run_test_command,
    'ngrok': _run_ngrok_command,
}


def main():
    parser = _build_argument_parser()
    args = parser.parse_args()
    tester = WebhookTester(args.port if hasattr(args, 'port') else DEFAULT_PORT)
    try:
        _COMMAND_HANDLERS[args.command](tester, args)
    except json.JSONDecodeError:
        print(ERROR_INVALID_JSON_DATA, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
