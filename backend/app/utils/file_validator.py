"""Uploaded-file validator: extension + magic-bytes + size cap."""
from __future__ import annotations

from fastapi import HTTPException, UploadFile

MAX_IMAGE_BYTES = 5 * 1024 * 1024        # 5 MB
MAX_PDF_BYTES = 25 * 1024 * 1024         # 25 MB
MAX_MEDIA_BYTES = 500 * 1024 * 1024      # 500 MB (audio/video)

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "gif", "svg"}
ALLOWED_PDF_EXT = {"pdf"}
ALLOWED_AUDIO_EXT = {"mp3", "wav", "aac", "m4a", "ogg"}
ALLOWED_VIDEO_EXT = {"mp4", "webm", "mov"}

# Magic-byte signatures (first N bytes)
_SIGS = {
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "gif": [b"GIF87a", b"GIF89a"],
    "webp": [b"RIFF"],  # + "WEBP" at byte 8
    "pdf": [b"%PDF-"],
    "mp3": [b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"],
    "mp4": [b"\x00\x00\x00", b"ftyp"],  # partial; ftyp at byte 4
    "webm": [b"\x1a\x45\xdf\xa3"],
}


def _ext(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _matches_sig(head: bytes, ext: str) -> bool:
    sigs = _SIGS.get(ext)
    if not sigs:
        return True  # no known sig; accept if extension ok
    for s in sigs:
        if head.startswith(s) or s in head[:32]:
            return True
    return False


async def validate_upload(
    file: UploadFile,
    kind: str = "image",  # image | pdf | audio | video | any
) -> bytes:
    """Read the whole file, validate size + extension + magic bytes, return bytes.

    Raises HTTPException on any failure so it can be used inline in routes.
    """
    ext = _ext(file.filename)
    if kind == "image":
        allowed, cap = ALLOWED_IMAGE_EXT, MAX_IMAGE_BYTES
    elif kind == "pdf":
        allowed, cap = ALLOWED_PDF_EXT, MAX_PDF_BYTES
    elif kind == "audio":
        allowed, cap = ALLOWED_AUDIO_EXT, MAX_MEDIA_BYTES
    elif kind == "video":
        allowed, cap = ALLOWED_VIDEO_EXT, MAX_MEDIA_BYTES
    else:
        allowed = ALLOWED_IMAGE_EXT | ALLOWED_PDF_EXT | ALLOWED_AUDIO_EXT | ALLOWED_VIDEO_EXT
        cap = MAX_MEDIA_BYTES

    if ext not in allowed:
        raise HTTPException(
            400, f"Extension .{ext or '?'} not allowed. Allowed: {sorted(allowed)}"
        )

    content = await file.read()
    if len(content) > cap:
        raise HTTPException(413, f"File exceeds size limit ({cap // (1024*1024)} MB)")
    if len(content) == 0:
        raise HTTPException(400, "Empty file")
    if not _matches_sig(content[:32], ext):
        raise HTTPException(400, f"File contents don't match extension .{ext}")

    # Reset stream in case the caller wants to re-read (SpooledTemporaryFile).
    try:
        await file.seek(0)
    except Exception:
        pass
    return content
