import asyncio

import httpx

from backend import max_integration


def test_package_upload_accepts_max_xml_receipt(monkeypatch):
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path == "/uploads":
            return httpx.Response(200, json={"url": "https://omub.okcdn.ru/upload.do?sig=opaque", "token": "file-token"})
        if request.url.host == "omub.okcdn.ru":
            return httpx.Response(200, text="<retval>1</retval>")
        return httpx.Response(200, json={"message": {"body": {"text": "sent"}}})

    transport = httpx.MockTransport(respond)
    monkeypatch.setenv("MAX_BOT_TOKEN", "test-token")
    monkeypatch.setattr(max_integration, "_client", lambda timeout: httpx.AsyncClient(transport=transport))

    asyncio.run(max_integration.send_package(123, b"zip-content", "12345678-test"))

    assert len(requests) == 3
    assert b'chuzhoe-mesto-12345678.zip' in requests[1].content
    assert b'"token":"file-token"' in requests[2].content


def test_package_upload_host_is_restricted():
    assert max_integration._upload_host_allowed("https://omub.okcdn.ru/upload.do")
    assert max_integration._upload_host_allowed("https://fu.oneme.ru/upload")
    assert not max_integration._upload_host_allowed("http://omub.okcdn.ru/upload.do")
    assert not max_integration._upload_host_allowed("https://omub.okcdn.ru.evil.example/upload")
    assert not max_integration._upload_host_allowed("https://127.0.0.1/upload")
