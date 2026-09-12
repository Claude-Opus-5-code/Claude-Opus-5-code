"""Validate and upload images in memory. No caller-supplied paths or remote fetch."""

import base64
import binascii
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from ._config import ProviderConfig
from ._transport import Transport, UpstreamFailure


@dataclass(frozen=True)
class Image:
    data: bytes = field(repr=False)
    format: str

    @property
    def mime(self) -> str:
        return f"image/{self.format}"


def decode_image(encoded: object, image_format: object, config: ProviderConfig) -> Image:
    if not isinstance(encoded, str) or not isinstance(image_format, str):
        raise UpstreamFailure("bad_request")
    fmt = image_format.lower()
    fmt = "jpeg" if fmt == "jpg" else fmt
    if fmt not in {"png", "jpeg", "webp"}:
        raise UpstreamFailure("bad_request")
    if not encoded or len(encoded) > 4 * ((config.max_image_bytes + 2) // 3):
        raise UpstreamFailure("bad_request")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise UpstreamFailure("bad_request") from None
    if not data or len(data) > config.max_image_bytes:
        raise UpstreamFailure("bad_request")
    # Verify basic format framing; pixel decoding remains the upstream's job.
    valid = {
        "png": len(data) >= 33
        and data.startswith(b"\x89PNG\r\n\x1a\n")
        and data[8:16] == b"\x00\x00\x00\rIHDR"
        and b"IEND" in data[-12:],
        "jpeg": len(data) >= 4 and data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"),
        "webp": len(data) >= 20
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
        and int.from_bytes(data[4:8], "little") == len(data) - 8,
    }[fmt]
    if not valid:
        raise UpstreamFailure("bad_request")
    return Image(data, fmt)


async def upload_image(wire: Transport, image: Image) -> list[dict[str, str]]:
    body = await wire.request(
        "POST",
        "chats/upload-files",
        files={
            "files": (f"image.{image.format}", image.data, image.mime),
        },
        data={"destination": "uploaded", "check_duplicates": "true", "model_type": ""},
    )
    files = body.get("files")
    if not isinstance(files, list) or not files or not isinstance(files[0], dict):
        raise UpstreamFailure("non_retryable_error")
    url = files[0].get("url")
    if not isinstance(url, str) or len(url) > 4096 or any(ord(c) <= 32 for c in url):
        raise UpstreamFailure("non_retryable_error")
    try:
        parsed = urlsplit(url)
        valid = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise UpstreamFailure("non_retryable_error")
    return [{"object_type": "image", "object_url": url}]
