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

import requests
import json
import html

from bs4 import BeautifulSoup
from functools import cached_property

try:
    from modules.consts import *
    from modules.exceptions import *
    from modules.locals import *
    from modules.progress_bars import *
    from modules.download import *
    from modules.sorting import *

except (ModuleNotFoundError, ImportError):
    from .modules.consts import *
    from .modules.exceptions import *
    from .modules.locals import *
    from .modules.progress_bars import *
    from .modules.download import *
    from .modules.sorting import *


class Video:
    def __init__(self, url):
        self.url = self.check_url(url)
        self.session = requests.Session()
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'}

        self.session.headers.update(headers)

        self.html_content = self.get_html_content()
        self.json_data = self.flatten_json(nested_json=self.extract_json_from_html())
        self.script_content = self.get_script_content()

    @classmethod
    def check_url(cls, url):
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
        return self.session.get(self.url).content.decode("utf-8")

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

    def get_available_qualities(self):
        response = self.session.get(self.m3u8_base_url)
        content = response.content.decode("utf-8")
        lines = content.splitlines()

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
        quality = self.fix_quality(quality)

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

    def get_segments(self, quality):

        quality = self.fix_quality(quality)

        # Some inspiration from PHUB (xD)
        base_url = self.m3u8_base_url
        new_segment = self.get_m3u8_by_quality(quality)
        # Split the base URL into components
        url_components = base_url.split('/')

        # Replace the last component with the new segment
        url_components[-1] = new_segment

        # Rejoin the components into the new full URL
        new_url = '/'.join(url_components)
        master_src = self.session.get(url=new_url).text

        urls = [l for l in master_src.splitlines()
                if l and not l.startswith('#')]

        for url in urls:
            url_components[-1] = url
            new_url = '/'.join(url_components)
            yield new_url

    @classmethod
    def fix_quality(cls, quality):
        # Needed for Porn Fetch

        if isinstance(quality, Quality):
            return quality

        else:
            if str(quality) == "best":
                return Quality.BEST

            elif str(quality) == "half":
                return Quality.HALF

            elif str(quality) == "worst":
                return Quality.WORST

    def download(self, downloader, quality, output_path, callback=None):
        """
        :param callback:
        :param downloader:
        :param quality:
        :param output_path:
        :return:
        """
        quality = self.fix_quality(quality)

        if callback is None:
            callback = Callback.text_progress_bar

        if downloader == default or str(downloader) == "default":
            default(video=self, quality=quality, path=output_path, callback=callback)

        elif downloader == threaded or str(downloader) == "threaded":
            threaded(video=self, quality=quality, path=output_path, callback=callback)

        elif downloader == FFMPEG or str(downloader) == "FFMPEG":
            FFMPEG(video=self, quality=quality, path=output_path, callback=callback)

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
    def upload_date(self) -> str:
        return html.unescape(self.json_data["uploadDate"])

    @cached_property
    def content_url(self) -> str:
        return html.unescape(self.json_data["contentUrl"])

    @cached_property
    def keywords(self) -> list:
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
    def uploader(self) -> str:
        return REGEX_VIDEO_UPLOADER.search(self.html_content).group(1)

    @cached_property
    def length(self) -> str:
        return REGEX_VIDEO_LENGTH.search(self.html_content).group(1)

    @cached_property
    def pornstars(self) -> list:
        return REGEX_VIDEO_PORNSTARS.findall(self.html_content)


class Client:

    @classmethod
    def get_video(cls, url):
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

        url = f"https://www.xvideos.com/?k={query}&sort={sorting_Sort}%&datef={sorting_Date}&durf={sorting_Time}&quality={sort_Quality}"
        urls = []
        for page in range(pages):
            response = requests.get(f"{url}&p={page}").content.decode("utf-8")
            urls_ = Client.extract_video_urls(response)

            for url in urls_:
                url = f"https://www.xvideos.com{url}"

                if REGEX_VIDEO_CHECK_URL.match(url):
                    urls.append(url)

        for id in urls:
            yield Video(id)
