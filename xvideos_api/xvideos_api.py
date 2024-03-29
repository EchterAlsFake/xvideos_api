"""
Copyright (C) 2024 Johannes Habel

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import json
import html

from bs4 import BeautifulSoup
from functools import cached_property
from base_api.base import Core, threaded, default, FFMPEG
from base_api.modules.quality import Quality

try:
    from modules.consts import *
    from modules.exceptions import *
    from modules.sorting import *

except (ModuleNotFoundError, ImportError):
    from .modules.consts import *
    from .modules.exceptions import *
    from .modules.sorting import *


class Video:
    def __init__(self, url):
        """
        :param url: (str) The URL of the video
        """
        self.url = self.check_url(url)
        self.html_content = self.get_html_content()
        self.json_data = self.flatten_json(nested_json=self.extract_json_from_html())
        self.script_content = self.get_script_content()
        self.quality_url_map = None
        self.available_qualities = None

    @classmethod
    def check_url(cls, url) -> str:
        """
        :param url: (str) The URL of the video
        :return: (str) The URL of the video, if valid, otherwise raises InvalidUrl Exception
        """
        match = REGEX_VIDEO_CHECK_URL.match(url)
        if match:
            return url

        else:
            raise InvalidUrl

    @classmethod
    def is_desired_script(cls, tag):
        if tag.name != "script":
            return False
        script_contents = ['html5player', 'setVideoTitle', 'setVideoUrlLow', 'setVideoUrlHigh']
        return all(content in tag.text for content in script_contents)

    def get_script_content(self):
        soup = BeautifulSoup(self.html_content, 'lxml')
        target_script = soup.find(self.is_desired_script)
        return target_script.text

    def get_html_content(self):
        return Core().get_content(self.url, headers=headers).decode("utf-8")

    def extract_json_from_html(self):
        soup = BeautifulSoup(self.html_content, 'lxml')
        script_tags = soup.find_all('script', {'type': 'application/ld+json'})

        combined_data = {}

        for script in script_tags:
            json_text = script.string.strip()
            data = json.loads(json_text)
            combined_data.update(data)
        cleaned_dictionary = self.flatten_json(combined_data)
        return cleaned_dictionary

    def flatten_json(self, nested_json, parent_key='', sep='_'):
        """
        Flatten a nested json dictionary. Duplicate keys will be overridden.

        :param nested_json: The nested JSON dictionary to be flattened.
        :param parent_key: The base key to use for the flattened keys.
        :param sep: The separator between nested keys.
        :return: A flattened dictionary.
        """
        items = []
        for k, v in nested_json.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_json(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def get_available_qualities(self) -> list:
        """
        :return: (list) List of available qualities
        """
        response = Core().get_content(self.m3u8_base_url, headers=headers).decode("utf-8")
        lines = response.splitlines()

        quality_url_map = {}
        base_qualities = ["250p", "360p", "480p", "720p", "1080p"]

        for line in lines:
            for quality in base_qualities:
                if f"hls-{quality}" in line:
                    quality_url_map[quality] = line

        self.quality_url_map = quality_url_map
        self.available_qualities = list(quality_url_map.keys())
        return self.available_qualities

    def get_m3u8_by_quality(self, quality):
        """
        :param quality: (str, Quality) The video quality
        :return: (str) The m3u8 URL for the given quality
        """
        quality = Core().fix_quality(quality)

        self.get_available_qualities()
        base_qualities = ["250p", "360p", "480p", "720p", "1080p"]
        if quality == Quality.BEST:
            selected_quality = max(self.available_qualities, key=lambda q: base_qualities.index(q))
        elif quality == Quality.WORST:
            selected_quality = min(self.available_qualities, key=lambda q: base_qualities.index(q))
        elif quality == Quality.HALF:
            sorted_qualities = sorted(self.available_qualities, key=lambda q: base_qualities.index(q))
            middle_index = len(sorted_qualities) // 2
            selected_quality = sorted_qualities[middle_index]

        return self.quality_url_map.get(selected_quality)

    def get_segments(self, quality) -> list:
        """
        :param quality: (str, Quality) The video quality
        :return: (list) A list of segments (the .ts files)
        """
        quality = Core().fix_quality(quality)
        segments = Core().get_segments(quality=quality, m3u8_base_url=self.m3u8_base_url)
        return segments

    def download(self, downloader, quality, path, callback=None):
        """
        :param callback:
        :param downloader:
        :param quality:
        :param output_path:
        :return:
        """
        quality = Core().fix_quality(quality)
        Core().download(video=self, quality=quality, path=path, callback=callback, downloader=downloader)

    @cached_property
    def m3u8_base_url(self) -> str:
        return REGEX_VIDEO_M3U8.search(self.script_content).group(1)

    @cached_property
    def title(self) -> str:
        return html.unescape(self.json_data["name"])

    @cached_property
    def description(self) -> str:
        return html.unescape(self.json_data["description"])

    @cached_property
    def thumbnail_url(self) -> str:
        return html.unescape(self.json_data["thumbnailUrl"])[0]

    @cached_property
    def publish_date(self) -> str:
        return html.unescape(self.json_data["uploadDate"])

    @cached_property
    def content_url(self) -> str:
        return html.unescape(self.json_data["contentUrl"])

    @cached_property
    def tags(self) -> list:
        return REGEX_VIDEO_TAGS.findall(self.html_content)

    @cached_property
    def views(self) -> str:
        return REGEX_VIDEO_VIEWS.search(self.html_content).group(1)

    @cached_property
    def likes(self) -> str:
        return REGEX_VIDEO_RATING_LIKES.search(self.html_content).group(1)

    @cached_property
    def dislikes(self) -> str:
        return REGEX_VIDEO_RATING_DISLIKES.search(self.html_content).group(1)

    @cached_property
    def rating_votes(self) -> str:
        return REGEX_VIDEO_RATING_VOTES.search(self.html_content).group(1)

    @cached_property
    def comment_count(self) -> str:
        return REGEX_VIDEO_COMMENT_COUNT.search(self.html_content).group(1)

    @cached_property
    def author(self) -> str:
        try:
            uploader = REGEX_VIDEO_UPLOADER.search(self.html_content).group(1)

        except AttributeError:
            uploader = "Unknown"

        return uploader

    @cached_property
    def length(self) -> str:
        return REGEX_VIDEO_LENGTH.search(self.html_content).group(1)

    @cached_property
    def pornstars(self) -> list:
        return REGEX_VIDEO_PORNSTARS.findall(self.html_content)


class Client:

    @classmethod
    def get_video(cls, url):
        """
        :param url: (str) The video URL
        :return: (Video) The video object
        """
        return Video(url)

    @classmethod
    def extract_video_urls(cls, html_content):
        # Parse the HTML content with BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')
        video_urls = []

        # Find all 'div' elements with the class 'thumb'
        thumb_divs = soup.find_all('div', class_='thumb')

        # Iterate over each 'thumb' div and extract the 'href' attribute from the 'a' tag within it
        for div in thumb_divs:
            a_tag = div.find('a', href=True)  # Find the first 'a' tag with an 'href' attribute
            if a_tag and a_tag['href']:  # Ensure the 'a' tag and its 'href' attribute exist
                video_urls.append(a_tag['href'])

        return video_urls

    @classmethod
    def search(cls, query, sorting_Sort: Sort = Sort.Sort_relevance, sorting_Date: SortDate = SortDate.Sort_all,
               sorting_Time: SortVideoTime = SortVideoTime.Sort_all, sort_Quality: SortQuality = SortQuality.Sort_all,
               pages=2):

        query = query.replace(" ", "+")

        base_url = f"https://www.xvideos.com/?k={query}&sort={sorting_Sort}%&datef={sorting_Date}&durf={sorting_Time}&quality={sort_Quality}"
        urls = []
        for page in range(pages):
            response = Core().get_content(f"{base_url}&p={page}", headers=headers).decode("utf-8")
            urls_ = Client.extract_video_urls(response)

            for url in urls_:
                url = f"https://www.xvideos.com{url}"

                if REGEX_VIDEO_CHECK_URL.match(url):
                    urls.append(url)

        for id in urls:
            yield Video(id)
