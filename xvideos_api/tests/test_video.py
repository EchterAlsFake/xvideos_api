import pytest
import asyncio
from ..xvideos_api import Client

@pytest.mark.asyncio
async def test_video():
    url = "https://www.xvideos.com/video79875801/wow_what_a_dick_how_about_ass_fucking_"
    # This URL will be used for all tests

    client = Client()
    video = await client.get_video(url)

    assert isinstance(video.title, str) and len(video.title) > 0
    assert isinstance(video.author, str) and len(video.author) > 0
    assert isinstance(video.length, str) and len(video.length) > 0
    assert isinstance(video.views, str) and len(video.views) > 0
    assert isinstance(video.comment_count, str) and len(video.comment_count) > 0
    assert isinstance(video.likes, str) and len(video.likes) > 0
    assert isinstance(video.dislikes, str) and len(video.dislikes) > 0
    assert isinstance(video.rating_votes, str) and len(video.rating_votes) > 0
    assert isinstance(video.description, str) and len(video.description) > 0
    assert isinstance(video.tags, list) and len(video.tags) > 0
    assert isinstance(video.thumbnail_url, str) and len(video.thumbnail_url) > 0
    assert isinstance(video.preview_video_url, str) and len(video.preview_video_url) > 0
    assert isinstance(video.publish_date, str) and len(video.publish_date) > 0
    assert isinstance(video.content_url, str) and len(video.content_url) > 0
    assert isinstance(video.pornstars, list) and len(video.pornstars) > 0
