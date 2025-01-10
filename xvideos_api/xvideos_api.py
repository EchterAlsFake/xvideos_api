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
import os
import math
import html
import json
import httpx
import logging
import argparse

from typing import Union
from bs4 import BeautifulSoup
from base_api.base import BaseCore
from functools import cached_property

try:
    from modules.consts import *
    from modules.exceptions import *
    from modules.sorting import *

except (ModuleNotFoundError, ImportError):
    from .modules.consts import *
    from .modules.exceptions import *
    from .modules.sorting import *

core = BaseCore()
logging.basicConfig(format='%(name)s %(levelname)s %(asctime)s %(message)s', datefmt='%I:%M:%S %p')
logger = logging.getLogger("XVIDEOS API")
logger.setLevel(logging.DEBUG)

def disable_logging():
    logger.setLevel(logging.CRITICAL)



class Video:
    def __init__(self, url):
        """
        :param url: (str) The URL of the video
        """
        self.url = self.check_url(url)
        self.html_content = self.get_html_content()

        if isinstance(self.html_content, httpx.Response):
            if self.html_content.status_code == 404:
                raise VideoUnavailable("The video is not available or the URL is incorrect.")

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
            raise InvalidUrl(f"Invalid Video URL: {url}")

    @classmethod
    def is_desired_script(cls, tag):
        if tag.name != "script":
            return False
        script_contents = ['html5player', 'setVideoTitle', 'setVideoUrlLow']
        return all(content in tag.text for content in script_contents)

    def get_script_content(self):
        soup = BeautifulSoup(self.html_content, features="html.parser")
        target_script = soup.find(self.is_desired_script)
        return target_script.text

    def get_html_content(self) -> Union[str, httpx.Response]:
        return core.fetch(self.url)

    def extract_json_from_html(self):
        soup = BeautifulSoup(self.html_content, features="html.parser")
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

    def get_segments(self, quality) -> list:
        """
        :param quality: (str, Quality) The video quality
        :return: (list) A list of segments (the .ts files)
        """
        segments = core.get_segments(quality=quality, m3u8_url_master=self.m3u8_base_url)
        return segments

    def download(self, downloader, quality, path="./", callback=None, no_title=False) -> bool:
        """
        :param callback:
        :param downloader:
        :param quality:
        :param path:
        :param no_title:
        :return:
        """
        if no_title is False:
            path = os.path.join(path, f"{self.title}.mp4")

        try:
            core.download(video=self, quality=quality, path=path, callback=callback, downloader=downloader)
            return True

        except AttributeError:
            logging.warning("Video doesn't have an HLS stream. Using legacy downloading instead...")
            core.legacy_download(path=path, callback=callback, url=self.cdn_url)
            return True

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
    def preview_video_url(self) -> str:
        thumb = html.unescape(self.json_data["thumbnailUrl"])[0]
        base_url = re.sub(r'/thumbs(169)?(xnxx)?(l*|poster)/', '/videopreview/', thumb[:thumb.rfind("/")])
        suffix = re.search(r'-(\d+)', base_url)
        base_url = re.sub(r'-(\d+)', '', base_url) if suffix else base_url
        return f"{base_url}_169{suffix.group(0) if suffix else ''}.mp4"

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

    @cached_property
    def embed_url(self) -> str:
        return REGEX_IFRAME.search(html.unescape(self.html_content)).group(1)

    @cached_property
    def cdn_url(self) -> str:
        return self.json_data["contentUrl"]


class Pornstar:
    def __init__(self, url):
        self.url = url
        base_content = core.fetch(f"{self.url}/videos/best/0")
        self.data = json.loads(base_content)

    @cached_property
    def total_videos(self):
        return int(self.data["nb_videos"])

    @cached_property
    def per_page(self):
        return int(self.data["nb_per_page"])

    @cached_property
    def total_pages(self):
        return math.ceil(self.total_videos / self.per_page)

    @cached_property
    def videos(self):
        for idx in range(0, self.total_pages):
            url_dynamic_javascript = core.fetch(f"{self.url}/videos/best/{idx}")
            data = json.loads(url_dynamic_javascript)

            u_values = [video["u"] for video in data["videos"]]
            for video in u_values:
                url = str(video).split("/")
                id = url[4]
                part_two = url[5]
                yield Video(f"https://www.xvideos.com/video.{id}/{part_two}")


class Client:

    @classmethod
    def get_video(cls, url: str) -> Video:
        """
        :param url: (str) The video URL
        :return: (Video) The video object
        """
        return Video(url)

    @classmethod
    def extract_video_urls(cls, html_content: str) -> list:
        # Parse the HTML content with BeautifulSoup
        soup = BeautifulSoup(html_content, features="html.parser")
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
    def search(cls, query: str, sorting_sort: Sort = Union[str, Sort.Sort_relevance],
               sorting_date: Union[str, SortDate] = SortDate.Sort_all,
               sorting_time: Union[str, SortVideoTime] = SortVideoTime.Sort_all,
               sort_quality: Union[str, SortQuality] = SortQuality.Sort_all) -> Video:

        query = query.replace(" ", "+")

        base_url = f"https://www.xvideos.com/?k={query}&sort={sorting_sort}%&datef={sorting_date}&durf={sorting_time}&quality={sort_quality}"

        for page in range(100):
            response = core.fetch(f"{base_url}&p={page}")
            urls_ = Client.extract_video_urls(response)

            for url in urls_:
                url = f"https://www.xvideos.com{url}"

                if REGEX_VIDEO_CHECK_URL.match(url):
                    yield Video(url)

    @classmethod
    def get_pornstar(cls, url) -> Pornstar:
        return Pornstar(url)


def main():
    parser = argparse.ArgumentParser(description="API Command Line Interface")
    parser.add_argument("--download", metavar="URL (str)", type=str, help="URL to download from")
    parser.add_argument("--quality", metavar="best,half,worst", type=str, help="The video quality (best,half,worst)",
                        required=True)
    parser.add_argument("--file", metavar="Source to .txt file", type=str,
                        help="(Optional) Specify a file with URLs (separated with new lines)")
    parser.add_argument("--output", metavar="Output directory", type=str, help="The output path (with filename)",
                        required=True)
    parser.add_argument("--downloader", type=str, help="The Downloader (threaded,ffmpeg,default)", required=True)
    parser.add_argument("--no-title", metavar="True,False", type=str,
                        help="Whether to apply video title automatically to output path or not", required=True)

    args = parser.parse_args()
    no_title = BaseCore().str_to_bool(args.no_title)
    if args.download:
        client = Client()
        video = client.get_video(args.download)
        video.download(quality=args.quality, path=args.output, downloader=args.downloader, no_title=no_title)

    if args.file:
        videos = []
        client = Client()

        with open(args.file, "r") as file:
            content = file.read().splitlines()

        for url in content:
            videos.append(client.get_video(url))

        for video in videos:
            video.download(quality=args.quality, path=args.output, downloader=args.downloader, no_title=no_title)


if __name__ == "__main__":
    main()
