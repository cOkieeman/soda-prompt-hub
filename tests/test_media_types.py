"""Media types must not depend on the host MIME database.

CPython's built-in MIME table has no `.webp` entry, so `mimetypes` only resolves it
through /etc/mime.types. Where that mapping is missing (Ubuntu 22.04, minimal images)
Starlette's FileResponse serves thumbnails as application/octet-stream and browsers
stop rendering them inline.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

import pytest

from prompt_hub.media import media_type_for


@pytest.fixture
def without_system_mime_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a host whose MIME database does not know webp."""
    monkeypatch.setattr(mimetypes, "guess_type", lambda *_args, **_kwargs: (None, None))


@pytest.mark.usefixtures("without_system_mime_database")
@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("thumb.webp", "image/webp"),
        ("thumb.WEBP", "image/webp"),
        ("frame.png", "image/png"),
        ("photo.jpg", "image/jpeg"),
        ("photo.JPEG", "image/jpeg"),
        ("anim.gif", "image/gif"),
        ("next.avif", "image/avif"),
    ],
)
def test_project_image_formats_have_fixed_media_types(
    filename: str,
    expected: str,
) -> None:
    assert media_type_for(Path(filename)) == expected


def test_unknown_extension_still_falls_back_to_mimetypes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mimetypes,
        "guess_type",
        lambda *_args, **_kwargs: ("application/x-test-archive", None),
    )
    assert media_type_for(Path("archive.zip")) == "application/x-test-archive"


@pytest.mark.usefixtures("without_system_mime_database")
def test_unmapped_extension_without_database_falls_back_to_octet_stream() -> None:
    assert media_type_for(Path("blob.bin")) == "application/octet-stream"
