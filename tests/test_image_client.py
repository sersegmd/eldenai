from __future__ import annotations
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.image_client import ImageBackendClient, ImageBackendError

async def run():
    client = ImageBackendClient()
    assert client.configured is False
    try:
        await client.generate("test", "768x768")
    except ImageBackendError as exc:
        assert "not configured" in str(exc)
    else:
        raise AssertionError("UI-only image backend must not generate")

def main():
    asyncio.run(run())
    print("Image interface-only backend: PASS")

if __name__ == "__main__": main()
