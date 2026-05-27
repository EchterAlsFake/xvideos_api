import pytest
from ..xvideos_api import Client



@pytest.mark.asyncio
async def test_pornstar():
    client = Client()
    pornstar = await client.get_pornstar("https://de.xvideos.com/pornstars/sweetie-fox1")

    assert isinstance(pornstar.total_videos, int)
    assert isinstance(pornstar.total_pages, int)
    idx = 0
    async for video in pornstar.videos(videos_concurrency=1, pages_concurrency=1):
        assert isinstance(video.title, str) and len(video.title) >= 3
        idx += 1
        if idx == 3:
            break
