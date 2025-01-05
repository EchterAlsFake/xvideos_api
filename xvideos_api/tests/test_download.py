import asyncio
import pytest
from ..xvideos_api import Client

@pytest.mark.asyncio
async def test_download():
    client = Client()

    url_1 = "https://de.xvideos.com/video.ufavdcma5da/regional/202/0/gilf_showing_her_new_sexy_new_years_eve_party_outfit_with_some_dirtytalk._watch_the_horny_granny_nude_at_the_end_ai-generated"
    url_2 = "https://de.xvideos.com/video.ufceveh7bfc/regional/202/0/called_a_whore_on_new_year_s_eve_-_stepsister_came_-_had_to_fuck_her_-_russian_amateur_with_conversations_and_subtitles"
    url_3 = "https://de.xvideos.com/video.ufdidkbdca0/regional/202/0/hot_milf_gives_handjob_from_behind_-_step_mom_helping_step_son_handmade._new_year_party"

    video_1 = await client.get_video(url_1)
    video_2 = await client.get_video(url_2)
    video_3 = await client.get_video(url_3)
    assert await video_1.download(downloader="threaded", quality="best") is True
    assert await video_2.download(downloader="threaded", quality="half") is True
    assert await video_3.download(downloader="threaded", quality="worst") is True
