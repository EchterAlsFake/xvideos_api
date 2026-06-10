import pytest
from ..xvideos_api import Client, Channel

url = "https://de.xvideos.com/video.ohplvhk02fd/meine_lesbische_freundin_hat_mich_beim_fremdgehen_mit_einem_zufalligen_typen_erwischt_aber_ich_kann_nicht_aufhoren_und_ficke_ihn_weiter_vor_ihren_augen_"
# This URL will be used for all tests

client = Client()
video = None

@pytest.mark.asyncio
async def test_get_video():
    global video
    video = await client.get_video(url)
    assert isinstance(video.title, str) and len(video.title) > 0
    assert isinstance(video.author, Channel)
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
