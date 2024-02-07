# XNXX API Documentation

> - Version 1.1
> - Author: Johannes Habel
> - Copryight (C) 2024
> - License: GPL 3
> - Dependencies: requests, lxml, bs4, ffmpeg-progress-yield 
> - Optional dependency: ffmpeg (installed in path)


# Important Notice
The ToS of xvideos.com clearly say, that using scrapers / bots isn't allowed.
> Using this API is on your risk. I am not liable for your actions!

# Table of Contents
- [Importing the API](#importing-the-api)
- [Initializing the Client](#initializing-the-client)
- [The Video object](#the-video-object)
    - [Attributes](#attributes)
    - [Downloading](#downloading-a-video)
    - [Custom callback](#custom-callback-for-downloading--videos)
- [Searching Videos](#searching)
    - [Basic Search](#basic-search)
    - [Using Filters](#using-filters)

- [Locals](#locals)
  - [Quality](#the-quality-object)

# Importing the API

#### To import all modules you should use the following:

```python
from xvideos_api.xvideos_api import Client, Quality
```

# Initializing the Client

- The Client is needed for all basic operations and will be used to handle everything.

```python
from xvideos_api.xvideos_api import Client

client = Client()

# Now you can fetch a Video object:

video = client.get_video("<video_url")
```


# The Video Object

The video object has the following values:

### Attributes

| Attribute      | Returns | is cached? |
|:---------------|:-------:|:----------:|
| .title         |   str   |    Yes     |
| .author        |   str   |    Yes     |
| .length        |   str   |    Yes     |
| .views         |   str   |    Yes     |
| .comment_count |   str   |    Yes     |
| .likes         |   str   |    Yes     |
| .dislikes      |   str   |    Yes     |
| .rating_votes  |   str   |    Yes     |
| .pornstars     |  list   |    Yes     |
| .description   |   str   |    Yes     |
| .tags          |  list   |    Yes     |
| .thumbnail_url |  list   |    Yes     |
| .publish_date  |   str   |    Yes     |
| .content_url   |   str   |    Yes     |

### Downloading a Video:

Explanation: 

Videos are downloaded using segments. These are extracted from the master m3u8 for a given Quality.
There are three ways of downloading videos:

- Default: fetching one by one segment
- FFMPEG: Let ffmpeg handle all this for you
- Threaded: Using multiple workers to fetch the segments (recommended!)

> If you get problems with video stuttering: Use FFMPEG!
> 
When downloading a video you can give a `downloader` argument which represents a downloader.

You can import the three downloaders using:

```python
from xvideos_api.modules.download import default, threaded, FFMPEG
from xvideos_api.xvideos_api import Client, Quality, Callback

client = Client()
video = client.get_video("...")
video.download(downloader=threaded, quality=Quality.BEST, output_path="./IdontKnow.mp4", callback=Callback.text_progress_bar) 
                                            # See Locals
# This will save the video in the current working directory with the filename "IdontKnow.mp4"
```

### Custom Callback for downloading  videos

You may want to specify a custom callback for downloading videos. Luckily for you, I made it as easy as
possible :)

1. Create a callback function, which takes `pos` and `total` as arguments.
2. `pos` represents the current amount of downloaded segments
3. `total` represents the total amount of segments

Here's an example:

```python
def custom_callback(pos, total):
    """This is an example of how you can implement the custom callback"""

    percentage = (pos / total) * 100
    print(f"Downloaded: {pos} segments / {total} segments ({percentage:.2f}%)")
    # You see it's really simple :)
```

When downloading a video, you can just specify your callback functions in the `callback` argument

# Searching

## Basic Search

```python
from xvideos_api.xvideos_api import Client

client = Client()
videos = client.search("Mia Khalifa", pages=2)

for video in videos:
  print(video.title)
```

- One Page contains 27 videos
- Search filters are by default the ones from xvideos

## Using Filters

```python
from xvideos_api.modules.sorting import SortDate, Sort, SortQuality, SortVideoTime
from xvideos_api.xvideos_api import Client

client = Client()
videos = Client.search("Mia Khalifa", pages=1, sorting_Date=SortDate.Sort_all, sort_Quality=SortQuality.Sort_720p,
                        sorting_Sort=Sort.Sort_relevance, sorting_Time=SortVideoTime.Sort_short)

# If you don't specify filters, the default from xvideos.com will be used!
```

- Sort: Sorts videos by relevance, views and stuff
- SortQuality: Sorts videos by their quality
- SortDate: Sorts videos by upload date
- SortVideoTime: Sorts videos by their length






# Locals

## The Quality Object

First: Import the Quality object:

```python
from xvideos_api.xvideos_api import Quality
```

There are three quality types:

- Quality.BEST
- Quality.HALF
- Quality.WORST

> - You can also pass a string instead of a Quality object. e.g instead of `Quality.BEST`, you can say `best`
> - Same goes for threading modes. Instead of `download.threaded` you can just say `threaded` as a string
