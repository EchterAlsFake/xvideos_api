"""
Copyright (C) 2024-2025 Johannes Habel

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
import httpx
import logging
import argparse

from itertools import islice
from functools import cached_property
from base_api.modules.config import RuntimeConfig
from base_api.base import BaseCore, setup_logger, ErrorVideo
from typing import Union, Generator, Optional, List, Callable
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

try:
    from modules.consts import *
    from modules.errors import *
    from modules.sorting import *

except (ModuleNotFoundError, ImportError):
    from .modules.consts import *
    from .modules.errors import *
    from .modules.sorting import *

"""page_urls = [urljoin(self.url, f"videos/best/{i}") for i in range(pages)]"""


class Helper:
    def __init__(self, core: BaseCore):
        super().__init__()
        self.core = core

    @staticmethod
    def chunked(iterable, size):
        """
        This function is used to limit page fetching, so that not all pages are fetched at once.
        """
        it = iter(iterable)
        while True:
            block = list(islice(it, size))
            if not block:
                return
            yield block

    def _get_video(self, url: str):
        return Video(url, core=self.core)

    def _make_video_safe(self, url: str):
        try:
            return Video(url, core=self.core)
        except Exception as e:
            return ErrorVideo(url, e)

    def iterator(self, page_urls: List[str] = None, extractor: Callable = None,
                 pages_concurrency: int = 5, videos_concurrency: int = 20):

        # Results: (page_idx, vid_idx) -> Video/ErrorVideo
        results = {}
        # Count of videos for each site (known after extractor) needed to map videos to their sequence number (to keep them in order)
        page_counts = {}

        # Tracks the Index of videos, because we need to keep them in the correct order while fetching in parallel
        next_page_idx = 0
        next_video_idx = 0

        def flush_ready():
            nonlocal next_page_idx, next_video_idx # Make the variables accessible from above

            while True:
                # Stop if we don't know the video count of the next page yet
                if next_page_idx not in page_counts:
                    return

                # If the site is finished, move on to the next one (keep the page workers always working)
                if next_video_idx >= page_counts[next_page_idx]:
                    next_page_idx += 1
                    next_video_idx = 0
                    continue

                key = (next_page_idx, next_video_idx)
                if key not in results:
                    return

                yield results.pop(key)
                next_video_idx += 1

        page_iter = iter(enumerate(page_urls))

        with ThreadPoolExecutor(max_workers=pages_concurrency) as page_executor, \
             ThreadPoolExecutor(max_workers=videos_concurrency) as video_executor:

            # In-Flight-Maps
            page_in_flight = {}   # future -> (page_idx, url)
            video_in_flight = {}  # future -> (page_idx, vid_idx)

            # Get URLs of pages and their index to start fetching
            for _ in range(pages_concurrency):
                try:
                    pidx, url = next(page_iter)
                    print(f"Fetching: {pidx}: {url}")

                except StopIteration:
                    break

                page_in_flight[page_executor.submit(self.core.fetch, url)] = (pidx, url)
                # These are the results of the fetched pages

            while page_in_flight or video_in_flight:
                # Waiting for a finished site or a video
                waiting_on = set(page_in_flight.keys()) | set(video_in_flight.keys())
                done, _ = wait(waiting_on, return_when=FIRST_COMPLETED)

                for fut in done:
                    # A site is finished, now extracting the videos
                    if fut in page_in_flight:
                        pidx, url = page_in_flight.pop(fut)
                        html = fut.result() # Get the HTML content

                        # Extract the video URLs from the extractor
                        video_urls = extractor(html)
                        print(f"Got {len(video_urls)} videos for: {url}")
                        # Keep track fo the total count of videos in the current site
                        page_counts[pidx] = len(video_urls)

                        # Start getting Video objects in parallel, but with the index and URL to keep the correct order
                        for vid_idx, vurl in enumerate(video_urls):
                            vf = video_executor.submit(self._make_video_safe, vurl)
                            video_in_flight[vf] = (pidx, vid_idx)

                        # After start the jobs above, we can already try flushing
                        yield from flush_ready()

                        # A site is finished, so we fetch the next one
                        try:
                            npidx, nurl = next(page_iter)
                            page_in_flight[page_executor.submit(self.core.fetch, nurl)] = (npidx, nurl)
                        except StopIteration:
                            pass

                    # A video is finished, so we save it in the results to flush (return) it later
                    elif fut in video_in_flight:
                        pidx, vid_idx = video_in_flight.pop(fut)
                        try:
                            results[(pidx, vid_idx)] = fut.result()
                        except Exception as e:
                            results[(pidx, vid_idx)] = ErrorVideo(f"<unknown:{pidx}/{vid_idx}>", e)

                        # return the things that are finished
                        yield from flush_ready()

            # clear anything left (shouldn't happen)
            yield from flush_ready()

class Video:
    def __init__(self, url, core: Optional[BaseCore] = None):
        """
        :param url: (str) The URL of the video
        """
        self.core = core
        self.url = self.check_url(url)
        self.logger = setup_logger(name="XVIDEOS API - [Video]", log_file=None, level=logging.ERROR)
        self.html_content = self.get_html_content()
        self.soup = BeautifulSoup(self.html_content, 'lxml')
        if isinstance(self.html_content, httpx.Response):
            if self.html_content.status_code == 404:
                raise VideoUnavailable("The video is not available or the URL is incorrect.")

        self.json_data = self.meta
        self.quality_url_map = None
        self.available_qualities = None

    def enable_logging(self, log_file: str = None, level = None, log_ip: str = None, log_port: int = None):
        self.logger = setup_logger(name="XVIDEOS API - [Video]", log_file=log_file, level=level, http_ip=log_ip, http_port=log_port)

    @cached_property
    def html_text(self) -> str:
        r = self.core.fetch(self.url)
        if isinstance(r, httpx.Response):
            if r.status_code == 404:
                raise VideoUnavailable("The video is not available or the URL is incorrect.")
            return r.text
        return r  # assume already a string

    @cached_property
    def soup(self) -> BeautifulSoup:
        # lxml is much faster than the default parser
        return BeautifulSoup(self.html_text, "lxml")

    @cached_property
    def script_content(self) -> str:
        # Find the one script we care about without reparsing
        def desired(tag):
            if tag.name != "script" or not tag.string:
                return False
            t = tag.string
            return ("html5player" in t) and ("setVideoTitle" in t) and ("setVideoUrlLow" in t)

        s = self.soup.find(desired)
        return s.string if s and s.string else ""

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

    @cached_property
    def json_data(self) -> dict:
        data = {}
        for s in self.soup.select('script[type="application/ld+json"]'):
            if not s.string:
                continue
            try:
                data.update(json.loads(s.string))
            except Exception:
                continue
        return data

    def get_html_content(self) -> Union[str, httpx.Response]:
        return self.core.fetch(self.url)

    @cached_property
    def meta(self) -> dict:
        j = self.json_data
        # Defensive access because JSON-LD varies
        return {
            "name": j.get("name"),
            "description": j.get("description"),
            "thumbnailUrl": (j.get("thumbnailUrl") or [None])[0] if isinstance(j.get("thumbnailUrl"), list) else j.get(
                "thumbnailUrl"),
            "uploadDate": j.get("uploadDate"),
            "contentUrl": j.get("contentUrl"),
        }

    def get_segments(self, quality) -> list:
        """
        :param quality: (str, Quality) The video quality
        :return: (list) A list of segments (the .ts files)
        """
        segments = self.core.get_segments(quality=quality, m3u8_url_master=self.m3u8_base_url)
        return segments

    def download(self, downloader, quality, path="./", callback=None, no_title=False, remux: bool = False, callback_remux=None) -> bool:
        """
        :param callback:
        :param downloader:
        :param quality:
        :param path:
        :param no_title:
        :param remux:
        :param callback_remux:
        :return:
        """
        if not no_title:
            path = os.path.join(path, f"{self.title}.mp4")

        try:
            self.core.download(video=self, quality=quality, path=path, callback=callback, downloader=downloader,
                               remux=remux, callback_remux=callback_remux)
            return True

        except AttributeError:
            self.logger.warning("Video doesn't have an HLS stream. Using legacy downloading instead...")
            self.core.legacy_download(path=path, callback=callback, url=self.cdn_url)
            return True

    @cached_property
    def m3u8_base_url(self) -> str:
        return REGEX_VIDEO_M3U8.search(self.script_content).group(1)

    @cached_property
    def title(self) -> str:
        return html.unescape(self.meta["name"]) if self.meta["name"] else ""

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
        a_tags = self.soup.find_all('a', class_="is-keyword btn btn-default")
        tags = []
        for tag in a_tags:
            tags.append(tag.text)

        return tags

    @cached_property
    def views(self) -> str:
        return self.soup.find('span', class_='icon-f icf-eye').next.text

    @cached_property
    def likes(self) -> str:
        return self.soup.find('span', class_='rating-good-nbr').text

    @cached_property
    def dislikes(self) -> str:
        return self.soup.find('span', class_='rating-bad-nbr').text

    @cached_property
    def rating_votes(self) -> str:
        return self.soup.find('span', class_='rating-total-txt').text

    @cached_property
    def comment_count(self) -> str:
        return self.soup.find('button', class_="comments tab-button").next.next.text

    @cached_property
    def author(self):
        """Returns the Channel object where the video was published on"""
        link = self.soup.find("li", class_="main-uploader").find('a')["href"]
        if not link.startswith("/profiles"):
            return Channel(url=f"https://xvideos.com/channels{link}", core=self.core)

        else:
            return Channel(url=f"https://xvideos.com{link}", core=self.core)

    @cached_property
    def length(self) -> str:
        return self.soup.find('span', class_="duration").text

    @cached_property
    def pornstars(self):
        """
        Returns the Pornstar objects for the Pornstars that are featured in the video
        """
        pornstars = self.soup.find_all('li', class_="model")
        urls = []
        for pornstar in pornstars:
            urls.append(f"https://xvideos.com{pornstar.next['href']}")

        for url in urls:
            yield Pornstar(url=url, core=self.core)

    @cached_property
    def embed_url(self) -> str:
        return REGEX_IFRAME.search(html.unescape(self.html_content)).group(1)

    @cached_property
    def cdn_url(self) -> str:
        return self.json_data["contentUrl"]


class Channel(Helper):
    """
    Returns the Channel object for a Channel. Please note, that the Channel object and the Pornstar object
    are almost identical, but I still differentiated them as two different classes, because TECHNICALLY they are
    different things.

    """
    def __init__(self, url: str, core: Optional[BaseCore], auto_init=True):
        super().__init__(core=core)
        self.core = core
        self.logger = setup_logger(name="XVIDEOS API - [Channel]", log_file=None, level=logging.ERROR)
        if "/channels/" not in url and "profiles" not in url:
            self.logger.warning("/channels/ not in URL. Trying to fix manually. This CAN lead to more errors!")
            self.url = url.replace("xvideos.com/", "xvideos.com/channels/")

        else:
            self.url = url

        base_content = self.core.fetch(f"{self.url}/videos/best/0")
        about_me_html = self.core.fetch(f"{self.url}#_tabAboutMe")
        self.bs4_about_me = BeautifulSoup(about_me_html, "lxml")
        self.data = json.loads(base_content)

    def enable_logging(self, name="XVIDEOS API - [Channel]", log_file=None, level=logging.DEBUG, log_ip: str = None, log_port: int = None):
        self.logger = setup_logger(name=name, log_file=log_file, level=level, http_ip=log_ip, http_port=log_port)

    @cached_property
    def name(self) -> str:
        return self.bs4_about_me.find('h2').find_all('strong', attrs={'class': 'text-danger'})[0].text

    @cached_property
    def thumbnail_url(self) -> str:
        return self.bs4_about_me.find('div', attrs={'class': 'profile-pic'}).find_all('img')[0]['src']

    @cached_property
    def total_videos(self):
        return int(self.data["nb_videos"])

    @cached_property
    def per_page(self):
        return int(self.data["nb_per_page"])

    @cached_property
    def total_pages(self):
        return math.ceil(self.total_videos / self.per_page)

    def videos(self, pages: int = 0, max_workers: int = 20):
        self.logger.debug(f"Channel has: {self.total_pages} pages...")

        yield from self.iterator(max_workers=max_workers)

    @cached_property
    def country(self) -> str:
        return self.bs4_about_me.find(id="pinfo-country").span.text.strip()

    @cached_property
    def profile_hits(self) -> str:
        return self.bs4_about_me.find(id="pinfo-profile-hits").span.text.strip()

    @cached_property
    def subscribers(self) -> str:
        return self.bs4_about_me.find(id="pinfo-subscribers").span.text.strip()

    @cached_property
    def total_video_views(self) -> str:
        return self.bs4_about_me.find(id="pinfo-video-views").span.text.strip()

    @cached_property
    def region(self) -> str:
        return self.bs4_about_me.find(id="pinfo-region").span.text.strip()

    @cached_property
    def signed_up(self) -> str:
        return self.bs4_about_me.find(id="pinfo-signedup").span.text.strip()

    @cached_property
    def last_activity(self) -> str:
        return self.bs4_about_me.find(id="pinfo-lastactivity").span.text.strip()

    @cached_property
    def worked_for_with(self):
        names = self.bs4_about_me.find(id="pinfo-workedfor").find_all('a')
        links = [a['href'] for a in names]
        for link in links:
            if not "profile" in link:
                return Channel(url=f"https://xvideos.com/channels{link}", core=self.core)

            else:
                return Channel(url=f"https://xvideos.com{link}", core=self.core)


class Pornstar(Helper):
    def __init__(self, url: str, core: Optional[BaseCore]):
        super().__init__(core=core)
        self.core = core
        self.url = self.check_url(url)
        base_content = self.core.fetch(f"{self.url}/videos/best/0")
        about_me_html = self.core.fetch(f"{self.url}#_tabAboutMe")
        self.bs4_about_me = BeautifulSoup(about_me_html, "lxml")
        self.data = json.loads(base_content)
        self.logger = setup_logger(name="XVIDEOS API - [Pornstar]", log_file=None, level=logging.ERROR)

    def enable_logging(self, log_file: str = None, level=None, log_ip: str = None, log_port: int = None):
        self.logger = setup_logger(name="XVIDEOS API - [Pornstar]", log_file=log_file, level=level, http_ip=log_ip, http_port=log_port)

    def check_url(self, url):
        if ("/pornstars/" not in url) and ("/model/" not in url):
            self.logger.error("URL doesn't contain '/pornstars/', seems like a channel URL or is generally invalid!")
            raise InvalidPornstar(
                "It seems like the Pornstar URL is invalid, please note, that channels are NOT supported!")

        return url

    @cached_property
    def name(self) -> str:
        return self.bs4_about_me.find('h2').find_all('strong', attrs={'class': 'text-danger'})[0].text

    @cached_property
    def thumbnail_url(self) -> str:
        return self.bs4_about_me.find('div', attrs={'class': 'profile-pic'}).find_all('img')[0]['src']

    @cached_property
    def total_videos(self):
        return int(self.data["nb_videos"])

    @cached_property
    def per_page(self):
        return int(self.data["nb_per_page"])

    @cached_property
    def total_pages(self):
        return math.ceil(self.total_videos / self.per_page)

    def videos(self, pages: int = 0, max_workers: int = 20):
        self.logger.debug(f"Pornstar has: {self.total_pages} pages...")
        yield from self.iterator(pages=pages, max_workers=max_workers)

    @cached_property
    def gender(self) -> str:
        return self.bs4_about_me.find(id="pinfo-sex").span.text.strip()

    @cached_property
    def age(self) -> str:
        """Returns the age of the Pornstar"""
        age = self.bs4_about_me.find(id="pinfo-age").span.text.strip()
        if int(age) < 18: # lmaooooo
            raise "Wait what????"

        return age

    @cached_property
    def country(self) -> str:
        """Returns the country of the Pornstar"""
        return self.bs4_about_me.find(id="pinfo-country").span.text.strip()

    @cached_property
    def profile_hits(self) -> str:
        """Returns the current profile hits count (don't know what that is lol)"""
        return self.bs4_about_me.find(id="pinfo-profile-hits").span.text.strip()

    @cached_property
    def subscriber_count(self) -> str:
        """Returns the current subscriber count of the pornstar"""
        return self.bs4_about_me.find(id="pinfo-subscribers").span.text.strip()

    @cached_property
    def total_videos_views(self) -> str:
        """Returns the total video views of the pornstar of all videos combined"""
        return self.bs4_about_me.find(id="pinfo-videos-views").span.text.strip()

    @cached_property
    def sign_up_date(self) -> str:
        """Returns the date where the pornstar signed up his / her account"""
        return self.bs4_about_me.find(id="pinfo-signedup").span.text.strip()

    @cached_property
    def last_activity(self) -> str:
        """Returns the date of the last activity of the Pornstar"""
        return self.bs4_about_me.find(id="pinfo-lastactivity").span.text.strip()

    @cached_property
    def video_tags(self) -> str:
        """Returns the video tags the pornstar is often featured in"""
        return self.bs4_about_me.find(id="pinfo-video-tags").span.text.strip()

    @cached_property
    def worked_for_with(self) -> Generator[Channel, None, None]:
        """
        Returns the channels the pornstar has worked with as a Channel object (Generator)
        """
        names = self.bs4_about_me.find(id="pinfo-workedfor").find_all('a')
        links = [a['href'] for a in names]
        for link in links:
            yield Channel(core=self.core, url=f"https://www.xvideos.com{link}")


class Client(Helper):
    def __init__(self, core: Optional[BaseCore] = None):
        super().__init__(core)
        self.core = core or BaseCore(config=RuntimeConfig())
        self.core.initialize_session()
        self.logger = setup_logger(name="XVIDEOS API - [Client]", log_file=None, level=logging.ERROR)

    def enable_logging(self, log_file: str = None, level=None, log_ip: str = None, log_port: int = None):
        self.logger = setup_logger(name="XVIDEOS API - [Client]", log_file=log_file, level=level, http_ip=log_ip, http_port=log_port)

    def get_video(self, url: str) -> Video:
        """
        :param url: (str) The video URL
        :return: (Video) The video object
        """
        return Video(url, core=self.core)

    def search(self, query: str, sorting_sort: Union[str, Sort.Sort_relevance] = Sort.Sort_relevance,
               sorting_date: Union[str, SortDate] = SortDate.Sort_all,
               sorting_time: Union[str, SortVideoTime] = SortVideoTime.Sort_all,
               sort_quality: Union[str, SortQuality] = SortQuality.Sort_all,
               pages: int = 30, videos_concurrency: int = 20,
               pages_concurrency: int = 5) -> Generator[Video, None, None]:

        query = query.replace(" ", "+")
        p = urlparse(f"https://www.xvideos.com/")
        qs = parse_qs(p.query)
        queries = {
            "k": query,
            "sort": sorting_sort,
            "datef": sorting_date,
            "durf": sorting_time,
            "quality": sort_quality
        }

        for key, value in queries.items():
            if value:
                qs[key] = [str(value)]

        new_query = urlencode(qs, doseq=True)
        url = urlunparse(p._replace(query=new_query))

        page_urls = [f"{url}&p={p}" for p in range(pages)]
        yield from self.iterator(page_urls=page_urls, extractor=extractor_html, videos_concurrency=videos_concurrency,
                                 pages_concurrency=pages_concurrency)


    def get_playlist(self, url: str, pages: int = 10, videos_concurrency: int = 20,
                     pages_concurrency: int = 5) -> Generator[Video, None, None]:
        page_urls = []

        for page in range(pages):
            page_urls.append(f"{url}/{page}")

        yield from self.iterator(page_urls=page_urls, extractor=extractor_html, videos_concurrency=videos_concurrency,
                                 pages_concurrency=pages_concurrency)

    def get_pornstar(self, url) -> Pornstar:
        return Pornstar(url, core=self.core)

    def get_channel(self, url) -> Channel:
        return Channel(url, core=self.core)


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
    playlist = Client().get_playlist(f"https://de.xvideos.com/favorite/37186029/everything", pages=200, pages_concurrency=5)
    for video in playlist:
        print(video.title)