"""HTTP bridge for KeenDNS: 192.168.2.32:8766 -> 127.0.0.1:8000.

Run separately from the application with Python 3.14. No third-party packages.
"""
from __future__ import annotations

import argparse
import base64
import hmac
import http.client
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM_HOST = "127.0.0.1"
UPSTREAM_PORT = 8000
MAX_REQUEST_BYTES = 40 * 1024 * 1024
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-connection", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade",
}
ALLOWED_HOSTS = {
    "test.agentsofcremlin.netcraze.pro",
    "test.agentsofcremlin.netcraze.pro:443",
    "192.168.2.32:8766",
    "127.0.0.1:8766",
}


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "ChuzhoeMestoBridge/1"
    protocol_version = "HTTP/1.0"  # End each response by closing the connection.

    def _authorized(self) -> bool:
        user = os.environ.get("TEST_PROXY_USER", "")
        password = os.environ.get("TEST_PROXY_PASSWORD", "")
        if not user or len(password) < 16:
            self.send_error(503, "Proxy access is not configured")
            return False
        expected = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        if hmac.compare_digest(self.headers.get("Authorization", ""), expected):
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="ChuzhoeMesto test"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        self.close_connection = True
        return False

    def _body(self) -> bytes:
        length = self.headers.get("Content-Length")
        transfer = self.headers.get("Transfer-Encoding", "").lower()
        if length is not None and transfer:
            raise ValueError("Conflicting request framing")
        if transfer:
            if transfer != "chunked":
                raise ValueError("Unsupported transfer encoding")
            chunks = []
            total = 0
            while True:
                line = self.rfile.readline(128)
                if not line.endswith(b"\r\n"):
                    raise ValueError("Invalid chunk header")
                size = int(line[:-2].split(b";", 1)[0], 16)
                if size == 0:
                    while self.rfile.readline(8192) not in (b"\r\n", b""):
                        pass
                    break
                total += size
                if total > MAX_REQUEST_BYTES:
                    raise OverflowError("Request too large")
                chunk = self.rfile.read(size)
                if len(chunk) != size or self.rfile.read(2) != b"\r\n":
                    raise ValueError("Incomplete chunk")
                chunks.append(chunk)
            return b"".join(chunks)
        if length is None:
            return b""
        size = int(length)
        if size < 0:
            raise ValueError("Invalid content length")
        if size > MAX_REQUEST_BYTES:
            raise OverflowError("Request too large")
        body = self.rfile.read(size)
        if len(body) != size:
            raise ValueError("Incomplete request body")
        return body

    def _forward(self) -> None:
        if not self.path.startswith("/") or self.path.startswith("//"):
            self.send_error(400, "Invalid request target")
            return
        host = self.headers.get("Host", "").lower()
        if host not in ALLOWED_HOSTS:
            self.send_error(400, "Unexpected host")
            return
        if not self._authorized():
            return
        try:
            body = self._body()
        except OverflowError:
            self.send_error(413, "Request too large")
            return
        except (ValueError, OSError):
            self.send_error(400, "Invalid request body")
            return
        headers = {
            key: value for key, value in self.headers.items()
            if key.lower() not in HOP_HEADERS | {"authorization", "content-length", "host", "x-forwarded-for", "x-forwarded-proto", "x-forwarded-host"}
        }
        headers["Host"] = host
        headers["X-Forwarded-For"] = self.client_address[0]
        headers["X-Forwarded-Proto"] = "https"
        headers["X-Forwarded-Host"] = host
        headers["Connection"] = "close"
        upstream = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=90)
        headers_sent = False
        try:
            upstream.request(self.command, self.path, body=body, headers=headers)
            response = upstream.getresponse()
            self.send_response(response.status, response.reason)
            for key, value in response.getheaders():
                if key.lower() not in HOP_HEADERS | {"server", "date"}:
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()
            headers_sent = True
            if self.command != "HEAD":
                while chunk := response.read(64 * 1024):
                    self.wfile.write(chunk)
        except (OSError, http.client.HTTPException):
            logging.exception("Application upstream unavailable")
            if not headers_sent and not self.wfile.closed:
                try:
                    self.send_error(502, "Application unavailable")
                except OSError:
                    pass
        finally:
            upstream.close()
            self.close_connection = True

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _forward


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen-host", default="192.168.2.32")
    parser.add_argument("--listen-port", type=int, default=8766)
    args = parser.parse_args()
    if not os.environ.get("TEST_PROXY_USER") or len(os.environ.get("TEST_PROXY_PASSWORD", "")) < 16:
        parser.error("Set TEST_PROXY_USER and a TEST_PROXY_PASSWORD of at least 16 characters")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    server = ThreadingHTTPServer((args.listen_host, args.listen_port), BridgeHandler)
    logging.info("KeenDNS bridge listening on %s:%s -> %s:%s", args.listen_host, args.listen_port, UPSTREAM_HOST, UPSTREAM_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
