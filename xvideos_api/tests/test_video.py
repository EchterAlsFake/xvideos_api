from ..xvideos_api import Client

url = "https://de.xvideos.com/video.ohplvhk02fd/meine_lesbische_freundin_hat_mich_beim_fremdgehen_mit_einem_zufalligen_typen_erwischt_aber_ich_kann_nicht_aufhoren_und_ficke_ihn_weiter_vor_ihren_augen_"
# This URL will be used for all tests

client = Client()
video = client.get_video(url)


def test_title():
    assert isinstance(video.title, str) and len(video.title) > 0


def test_uploader():
    assert isinstance(video.author, str) and len(video.author) > 0


def test_length():
    assert isinstance(video.length, str) and len(video.length) > 0


def test_views():
    assert isinstance(video.views, str) and len(video.views) > 0


def test_comment_count():
    assert isinstance(video.comment_count, str) and len(video.comment_count) > 0


def test_likes():
    assert isinstance(video.likes, str) and len(video.likes) > 0


def test_dislikes():
    assert isinstance(video.dislikes, str) and len(video.dislikes) > 0


def test_rating_votes():
    assert isinstance(video.rating_votes, str) and len(video.rating_votes) > 0


def test_description():
    assert isinstance(video.description, str) and len(video.description) > 0


def test_tags():
    assert isinstance(video.tags, list) and len(video.tags) > 0


def test_thumbnail_url():
    assert isinstance(video.thumbnail_url, str) and len(video.thumbnail_url) > 0


def test_preview_video_url():
    assert isinstance(video.preview_video_url, str) and len(video.preview_video_url) > 0


def test_publish_date():
    assert isinstance(video.publish_date, str) and len(video.publish_date) > 0


def test_content_url():
    assert isinstance(video.content_url, str) and len(video.content_url) > 0


def test_pornstars():
    assert isinstance(video.pornstars, list) and len(video.pornstars) > 0
