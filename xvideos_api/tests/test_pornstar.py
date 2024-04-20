from ..xvideos_api import Client

client = Client()
pornstar = client.get_pornstar("https://de.xvideos.com/pornstars/sweetie-fox1")


def test_pornstar():
    assert isinstance(pornstar.total_videos, int)
    assert isinstance(pornstar.total_pages, int)

    for idx, video in enumerate(pornstar.videos):
        assert isinstance(video.title, str) and len(video.title) >= 3
        if idx == 3:
            break
