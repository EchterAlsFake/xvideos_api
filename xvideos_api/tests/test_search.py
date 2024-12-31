from ..xvideos_api import Client, Sort, SortVideoTime, SortQuality, SortDate, VideoUnavailable
import pytest

# Initialize client and query
client = Client()
query = "Mia Khalifa"

def validate_video_objects(videos):
    """Helper function to validate video objects."""
    for idx, video in enumerate(videos):
        try:
            print(video.title)
            assert isinstance(video.title, str) and len(video.title) > 0, f"Invalid video title at index {idx}."
            if idx == 3:  # Validate up to 4 videos for brevity
                break

        except VideoUnavailable:
            break # Expected


@pytest.mark.parametrize("sort_option", [
    Sort.Sort_rating,
    Sort.Sort_relevance,
    Sort.Sort_views,
    Sort.Sort_length,
    Sort.Sort_random,
    Sort.Sort_upload_date,
])
def test_sort_search(sort_option):
    """Test sorting by different Sort options."""
    videos = client.search(query, sorting_sort=sort_option)
    validate_video_objects(videos)

@pytest.mark.parametrize("time_option", [
    SortVideoTime.Sort_long,
    SortVideoTime.Sort_all,
    SortVideoTime.Sort_short,
    SortVideoTime.Sort_middle,
    SortVideoTime.Sort_really_long,
    SortVideoTime.Sort_long_10_20min,
])
def test_sort_video_time_search(time_option):
    """Test sorting by different SortVideoTime options."""
    videos = client.search(query, sorting_time=time_option)
    validate_video_objects(videos)

@pytest.mark.parametrize("quality_option", [
    SortQuality.Sort_720p,
    SortQuality.Sort_all,
    SortQuality.Sort_1080_plus,
])
def test_sort_quality_search(quality_option):
    """Test sorting by different SortQuality options."""
    videos = client.search(query, sort_quality=quality_option)
    validate_video_objects(videos)

@pytest.mark.parametrize("date_option", [
    SortDate.Sort_all,
    SortDate.Sort_week,
    SortDate.Sort_month,
    SortDate.Sort_last_3_days,
    SortDate.Sort_last_3_months,
    SortDate.Sort_last_6_months,
])
def test_sort_date_search(date_option):
    """Test sorting by different SortDate options."""
    videos = client.search(query, sorting_date=date_option)
    validate_video_objects(videos)

def test_base_search():
    """Test basic search functionality."""
    videos = client.search(query)
    validate_video_objects(videos)

# Refactored by ChatGPT lol