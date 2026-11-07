import json
import threading
import urllib.error
import urllib.request

import pytest

from kaznlp import __version__
from kaznlp.server import make_server


@pytest.fixture()
def base_url():
    httpd = make_server("127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def request(url, data=None):
    body = None if data is None else data if isinstance(data, bytes) else json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


def test_health(base_url):
    assert request(f"{base_url}/health") == (200, {"status": "ok", "version": __version__})


def test_clean_single_text(base_url):
    status, body = request(f"{base_url}/clean", {"text": "Қaзақстан, тел +7 701 123 45 67"})
    assert status == 200
    (result,) = body["results"]
    assert result["normalized"].startswith("Қазақстан")
    assert "<PHONE>" in result["scrubbed"] and "+7 701" not in result["scrubbed"]
    assert result["pii"] == ["PHONE"]


def test_clean_batch(base_url):
    status, body = request(f"{base_url}/clean", {"texts": ["жақсы", "a@b.kz"]})
    assert status == 200
    assert [r["pii"] for r in body["results"]] == [[], ["EMAIL"]]


@pytest.mark.parametrize("payload", [b"not json", {"txt": "x"}, {"texts": [1, 2]}, [1]])
def test_clean_rejects_bad_input(base_url, payload):
    status, body = request(f"{base_url}/clean", payload)
    assert status == 400 and "error" in body


def test_unknown_paths(base_url):
    assert request(f"{base_url}/nope")[0] == 404
    assert request(f"{base_url}/nope", {"text": "x"})[0] == 404
