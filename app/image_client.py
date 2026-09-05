from __future__ import annotations

from dataclasses import dataclass


class ImageBackendError(RuntimeError):
    pass


class ImageModerationBlocked(ImageBackendError):
    pass


@dataclass
class GeneratedImage:
    data: bytes
    model: str = "not-configured"
    content_type: str = "image/png"


class ImageBackendClient:
    """Stable interface for the future image API.

    Replace `generate` when a suitable provider is selected. Keeping this
    boundary prevents the Telegram UI and Creator workflow from depending on
    a vendor-specific SDK.
    """

    configured = False

    async def generate(self, prompt: str, size: str) -> GeneratedImage:
        raise ImageBackendError("Image generation backend is not configured")
