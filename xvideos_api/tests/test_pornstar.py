import asyncio

import pytest
from ..xvideos_api import Client

@pytest.mark.asyncio
async def test_pornstar():
    client = Client()
    pornstar = await client.get_pornstar("https://de.xvideos.com/pornstars/sweetie-fox1")

    assert isinstance(pornstar.total_videos, int)
    assert isinstance(pornstar.total_pages, int)

    for idx, video in enumerate(await pornstar.videos):
        assert isinstance(video.title, str) and len(video.title) >= 3
        if idx == 3:
            break
