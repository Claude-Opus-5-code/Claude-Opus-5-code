"""Image validation and multipart upload use synthetic fixtures and mocks only."""

import base64
import json
import time
from uuid import uuid4

import httpx
import pytest

from providers.syntx._accounts import AccountPool
from providers.syntx._config import ProviderConfig
from providers.syntx._images import decode_image
from providers.syntx._transport import UpstreamFailure
from providers.syntx._upstream import generate

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aV1cAAAAASUVORK5CYII="


@pytest.mark.parametrize(
    "encoded,fmt",
    [
        ("%%%", "png"),
        ("", "png"),
        (None, "png"),
        (PNG, None),
        (PNG, "gif"),
        (PNG, "jpeg"),
        (base64.b64encode(b"not an image").decode(), "png"),
    ],
)
def test_bad_image_inputs(encoded, fmt):
    with pytest.raises(UpstreamFailure) as exc:
        decode_image(encoded, fmt, ProviderConfig())
    assert exc.value.kind == "bad_request"


def test_size_limit_and_safe_representation():
    with pytest.raises(UpstreamFailure):
        decode_image(PNG, "png", ProviderConfig(max_image_bytes=10))
    image = decode_image(PNG, "PNG", ProviderConfig())
    assert image.format == "png"
    assert image.mime == "image/png"
    assert "data=" not in repr(image)


@pytest.mark.parametrize(
    "upload_response,kind",
    [
        ({"files": [{"url": "https://assets.example.invalid/image.png"}]}, None),
        ({"files": []}, "non_retryable_error"),
        ({"files": [{"url": "file:///secret"}]}, "non_retryable_error"),
        (
            {"files": [{"url": "https://user:password@example.invalid/image"}]},
            "non_retryable_error",
        ),
    ],
)
async def test_upload_and_generation_files(tmp_path, upload_response, kind):
    cfg = ProviderConfig(state_dir=tmp_path, poll_interval=0.001, maintenance_enabled=False)
    pool = AccountPool(cfg)
    await pool.add_authorized([{"token": "test", "status": "active"}], time.monotonic() + 1)
    stages = []

    def respond(request):
        stages.append(request.url.path)
        if request.url.path.endswith("/chats"):
            return httpx.Response(201, json={"uuid": str(uuid4())})
        if request.url.path.endswith("/upload-files"):
            assert b'name="files"' in request.content
            assert b"Content-Type: image/png" in request.content
            assert base64.b64decode(PNG) in request.content
            return httpx.Response(200, json=upload_response)
        if request.url.path.endswith("/generate"):
            assert json.loads(request.content)["files"] == [
                {"object_type": "image", "object_url": "https://assets.example.invalid/image.png"}
            ]
            return httpx.Response(200, json={"job_id": "j"})
        return httpx.Response(
            200,
            json={
                "messages": [
                    {
                        "author_id": -1,
                        "message_object": [
                            {"object_type": "text", "completed": True, "object_text": "description"}
                        ],
                    }
                ]
            },
        )

    call = generate(
        model="grok-4.6",
        text="describe",
        timeout_ms=500,
        config=cfg,
        pool=pool,
        image=decode_image(PNG, "png", cfg),
        transport=httpx.MockTransport(respond),
    )
    if kind:
        with pytest.raises(UpstreamFailure) as exc:
            await call
        assert exc.value.kind == kind
        assert not any(stage.endswith("/generate") for stage in stages)
    else:
        assert (await call).text == "description"
        assert len(stages) == 4
