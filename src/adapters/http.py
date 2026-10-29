"""PUBG HTTP boundary; authentication stays outside application objects and diagnostics."""

import gzip
import json
from dataclasses import dataclass
import requests
from .credentials import API, api_key
from src.domain.errors import TransportError


@dataclass(frozen=True)
class HttpReply:
    status_code: int
    content: bytes

    def raise_for_status(self):
        if self.status_code >= 400:
            raise TransportError("HTTP_REQUEST_FAILED")

    def json(self):
        return json.loads(self.content)


class PubgHttp:
    def __init__(self, files, paths):
        self.files, self.paths = files, paths
        self._key = None

    def authorize(self):
        self._key = api_key()

    def request(self, path):
        try:
            response = requests.get(
                API + path,
                headers={
                    "Authorization": f"Bearer {self._key}",
                    "Accept": "application/vnd.api+json",
                },
                timeout=30,
            )
        except requests.RequestException:
            raise TransportError("HTTP_REQUEST_FAILED") from None
        return HttpReply(response.status_code, response.content)

    def get(self, path, raw_path=None):
        self.authorize()
        response = self.request(path)
        response.raise_for_status()
        if raw_path is not None:
            self.files.write_once(raw_path, response.content)
        return response.json()

    def download_telemetry(
        self, url, match_id, *, version="v1", run_id=None, compatibility_copy=True
    ):
        try:
            with requests.get(
                url, headers={"Accept-Encoding": "gzip"}, timeout=60, stream=True
            ) as response:
                response.raise_for_status()
                response.raw.decode_content = False
                body = response.raw.read()
        except requests.RequestException:
            raise TransportError("HTTP_REQUEST_FAILED") from None
        compressed = body[:2] == b"\x1f\x8b"
        base = self.paths.bronze / version
        if run_id:
            base /= run_id
        self.files.write_once(
            base / "telemetry" / f"{match_id}{'.json.gz' if compressed else '.json'}", body
        )
        decoded = gzip.decompress(body) if compressed else body
        json.loads(decoded)
        if compatibility_copy:
            self.files.write_bytes(self.paths.data / f"{match_id}.telemetry.json", decoded)
        return "gzip" if compressed else "json"
