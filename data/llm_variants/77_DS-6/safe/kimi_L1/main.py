"""Utility for testing webhooks locally.

A small HTTP server records the most recent POSTed JSON payload, curl is
used to send test requests, and the public HTTPS URL of a local ngrok
agent can be looked up.
"""

import argparse
import json
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Dict, Optional

_DEFAULT_PORT = 8000
_CURL_BASE_COMMAND = ["curl", "-X", "POST", "--fail", "--silent", "--show-error"]
_JSON_CONTENT_TYPE_HEADER = "Content-Type: application/json"
_NGROK_TUNNELS_API_URL = "http://localhost:4040/api/tunnels"
_HTTPS_PROTOCOL = "https"


class WebhookTester:
    """Receive webhook payloads on a local server and send test requests."""

    def __init__(self, port: int = 8000):
        self.port = port
        self.last_payload: Optional[Dict] = None
        self.server_thread: Optional[Thread] = None
        self.server: Optional[HTTPServer] = None

    class RequestHandler(BaseHTTPRequestHandler):
        """Record the JSON body of every incoming POST request."""

        def do_POST(self):
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            self.server.webhook_tester.last_payload = json.loads(post_data.decode())
            self.send_response(200)
            self.end_headers()

    def start_server(self):
        """Start the webhook server on a background daemon thread."""
        handler = self.RequestHandler
        handler.server = self
        self.server = HTTPServer(("", self.port), handler)
        # Let the request handler record payloads on this tester instance.
        self.server.webhook_tester = self
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

    def stop_server(self):
        """Shut the server down and wait for its thread to finish."""
        if self.server:
            self.server.shutdown()
            self.server_thread.join()

    def test_curl_request(self, url: str, data: Optional[Dict] = None) -> str:
        """POST to ``url`` with curl and return its output or error message."""
        try:
            cmd = self._build_curl_command(url, data)
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            return result.stdout if result.returncode == 0 else result.stderr
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"

    @staticmethod
    def _build_curl_command(url: str, data: Optional[Dict]) -> list:
        """Assemble the curl command line for a POST to ``url``."""
        cmd = list(_CURL_BASE_COMMAND)
        parsed_url = urllib.parse.urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise ValueError("Invalid URL format")
        if data:
            cmd.extend(["--data-binary", json.dumps(data)])
            cmd.extend(["-H", _JSON_CONTENT_TYPE_HEADER])
        cmd.append(url)
        return cmd

    def generate_ngrok_url(self) -> str:
        """Return the public HTTPS URL exposed by the local ngrok agent."""
        try:
            result = subprocess.run(
                ["curl", "-s", _NGROK_TUNNELS_API_URL],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            tunnels = json.loads(result.stdout)["tunnels"]
            https_tunnel = next((t for t in tunnels if t["proto"] == _HTTPS_PROTOCOL))
            return https_tunnel["public_url"]
        except json.JSONDecodeError:
            return "Error: Invalid response from ngrok"
        except StopIteration:
            return "Error: No HTTPS tunnel found"
        except Exception as e:
            return f"Error: {str(e)}"


def _create_argument_parser() -> argparse.ArgumentParser:
    """Build the parser for the command-line interface."""
    parser = argparse.ArgumentParser(description="Webhook Testing Utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server_parser = subparsers.add_parser("server", help="Start webhook server")
    server_parser.add_argument(
        "--port", type=int, default=_DEFAULT_PORT, help="Port to listen on"
    )

    test_parser = subparsers.add_parser("test", help="Test webhook URL")
    test_parser.add_argument("url", help="URL to test")
    test_parser.add_argument("--data", help="JSON data to send")

    subparsers.add_parser("ngrok", help="Get ngrok URL")

    return parser


def _run_server_command(tester: WebhookTester, port: int) -> None:
    """Run the webhook server until interrupted with Ctrl+C."""
    tester.start_server()
    print(f"Server running on port {port}. Press Ctrl+C to stop...")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        tester.stop_server()


def _run_test_command(tester: WebhookTester, url: str, data_option: Optional[str]) -> None:
    """Send a test request and show the last payload the server received."""
    data = json.loads(data_option) if data_option else None
    result = tester.test_curl_request(url, data)
    print(result)
    if tester.last_payload:
        print("\nLast received payload:", json.dumps(tester.last_payload, indent=2))


def main():
    parser = _create_argument_parser()
    args = parser.parse_args()
    tester = WebhookTester(args.port if hasattr(args, "port") else _DEFAULT_PORT)
    try:
        if args.command == "server":
            _run_server_command(tester, args.port)
        elif args.command == "test":
            _run_test_command(tester, args.url, args.data)
        elif args.command == "ngrok":
            print(tester.generate_ngrok_url())
    except json.JSONDecodeError:
        print("Error: Invalid JSON data", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
