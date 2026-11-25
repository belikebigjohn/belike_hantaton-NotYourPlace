"""In-memory checks for the fixed KeenDNS-to-application bridge."""
import io
import unittest
from email.message import Message
from unittest.mock import patch

from scripts import keen_proxy


def handler(method="POST", body=b"photo-bytes"):
    instance = object.__new__(keen_proxy.BridgeHandler)
    instance.command = method
    instance.path = "/api/analyze"
    instance.client_address = ("192.168.2.1", 5000)
    instance.headers = Message()
    instance.headers["Host"] = "test.agentsofcremlin.netcraze.pro"
    instance.headers["Content-Length"] = str(len(body))
    instance.rfile = io.BytesIO(body)
    instance.wfile = io.BytesIO()
    instance.events = []
    instance.send_response = lambda status, reason=None: instance.events.append(("status", status))
    instance.send_header = lambda name, value: instance.events.append((name, value))
    instance.end_headers = lambda: None
    return instance


class FakeResponse:
    status = 201
    reason = "Created"

    def __init__(self):
        self.chunks = iter((b"ok", b""))

    def getheaders(self):
        return [("Content-Length", "2"), ("Set-Cookie", "session=abc; HttpOnly")]

    def read(self, _size):
        return next(self.chunks)


class FakeConnection:
    def __init__(self):
        self.request_args = None

    def request(self, *args, **kwargs):
        self.request_args = (args, kwargs)

    def getresponse(self):
        return FakeResponse()

    def close(self):
        pass


class KeenProxyTest(unittest.TestCase):
    def test_forwards_body_and_cookie(self):
        proxy = handler()
        proxy.headers["X-Forwarded-Proto"] = "http"
        upstream = FakeConnection()
        with patch.object(keen_proxy.http.client, "HTTPConnection", return_value=upstream):
            proxy._forward()
        args, kwargs = upstream.request_args
        self.assertEqual(args, ("POST", "/api/analyze"))
        self.assertEqual(kwargs["body"], b"photo-bytes")
        self.assertEqual(kwargs["headers"]["X-Forwarded-Proto"], "https")
        self.assertEqual(kwargs["headers"]["X-Forwarded-For"], "192.168.2.1")
        self.assertEqual(kwargs["headers"]["Host"], "127.0.0.1:8000")
        self.assertIn(("Set-Cookie", "session=abc; HttpOnly"), proxy.events)
        self.assertEqual(proxy.wfile.getvalue(), b"ok")

    def test_rejects_oversized_request_before_reading_it(self):
        proxy = handler(body=b"")
        proxy.headers.replace_header("Content-Length", str(keen_proxy.MAX_REQUEST_BYTES + 1))
        with self.assertRaises(OverflowError):
            proxy._body()


if __name__ == "__main__":
    unittest.main()
