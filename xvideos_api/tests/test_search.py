from ..xvideos_api import Client, Sort, SortVideoTime, SortQuality, SortDate

# This is a deep test for the searching functionalities...

client = Client()
query = "Mia Khalifa"


def video_object_test(object):
    for idx, video in enumerate(object):
        assert isinstance(video.title, str) and len(video.title) > 0

        if idx == 3:
            break


def test_base_search():
    videos = client.search(query, pages=1)
    for video in videos:
        assert isinstance(video.title, str) and len(video.title) > 0


def test_Sort_search():
    videos = client.search(query, sorting_Sort=Sort.Sort_rating)
    videos_2 = client.search(query, sorting_Sort=Sort.Sort_relevance)
    videos_3 = client.search(query, sorting_Sort=Sort.Sort_views)
    videos_4 = client.search(query, sorting_Sort=Sort.Sort_length)
    videos_5 = client.search(query, sorting_Sort=Sort.Sort_random)
    videos_6 = client.search(query, sorting_Sort=Sort.Sort_upload_date)

    video_object_test(videos)
    video_object_test(videos_2)
    video_object_test(videos_3)
    video_object_test(videos_4)
    video_object_test(videos_5)
    video_object_test(videos_6)


def test_SortVideoTime_search():
    videos = client.search(query, pages=1, sorting_Time=SortVideoTime.Sort_long)
    videos_2 = client.search(query, pages=1, sorting_Time=SortVideoTime.Sort_all)
    videos_3 = client.search(query, pages=1, sorting_Time=SortVideoTime.Sort_short)
    videos_4 = client.search(query, pages=1, sorting_Time=SortVideoTime.Sort_middle)
    videos_5 = client.search(query, pages=1, sorting_Time=SortVideoTime.Sort_really_long)
    videos_6 = client.search(query, pages=1, sorting_Time=SortVideoTime.Sort_long_10_20min)



    video_object_test(videos)
    video_object_test(videos_2)
    video_object_test(videos_3)
    video_object_test(videos_4)
    video_object_test(videos_5)
    video_object_test(videos_6)


def test_SortQuality_search():
    videos = client.search(query, pages=1, sort_Quality=SortQuality.Sort_720p)
    videos_2 = client.search(query, pages=1, sort_Quality=SortQuality.Sort_all)
    videos_3 = client.search(query, pages=1, sort_Quality=SortQuality.Sort_1080_plus)

    video_object_test(videos)
    video_object_test(videos_2)
    video_object_test(videos_3)


def test_SortDate_search():
    videos = client.search(query, pages=1, sorting_Date=SortDate.Sort_all)
    videos_2 = client.search(query, pages=1, sorting_Date=SortDate.Sort_week)
    videos_3 = client.search(query, pages=1, sorting_Date=SortDate.Sort_month)
    videos_4 = client.search(query, pages=1, sorting_Date=SortDate.Sort_last_3_days)
    videos_5 = client.search(query, pages=1, sorting_Date=SortDate.Sort_last_3_months)
    videos_6 = client.search(query, pages=1, sorting_Date=SortDate.Sort_last_6_months)

    video_object_test(videos)
    video_object_test(videos_2)
    video_object_test(videos_3)
    video_object_test(videos_4)
    video_object_test(videos_5)
    video_object_test(videos_6)






