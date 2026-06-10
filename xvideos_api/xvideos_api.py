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
import logging
import asyncio
import argparse
import threading
import traceback


from functools import cached_property
from typing import Generator, AsyncGenerator
from base_api.modules.type_hints import DownloadReport
from curl_cffi.requests import Response, AsyncSession
from base_api.base import BaseCore, setup_logger, Helper
from base_api.modules.static_functions import str_to_bool
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from base_api.modules.errors import InvalidProxy, BotProtectionDetected, UnknownError,NetworkingError

try:
    import lxml
    parser = "lxml" # Faster speeds, but more dependencies

except (ModuleNotFoundError, ImportError):
    parser = "html.parser" # Fallback to classic HTML parser (will work fine)

try:
    from modules.consts import *
    from modules.errors import *
    from modules.sorting import *
    from modules.type_hints import *

except (ModuleNotFoundError, ImportError):
    from .modules.consts import *
    from .modules.errors import *
    from .modules.sorting import *
    from .modules.type_hints import *


async def get_html_content(core: BaseCore, url: str) -> str | None | dict:
    # What should I do here?
    try:
        content = await core.fetch(url)
        if isinstance(content, str):
            return content

        if isinstance(content, Response):
            if content.status_code == 404:
                raise NotFound(f"Server returned 404 for: {url}")

    except NetworkingError as e:
        raise NetworkError(str(e)) from e

    except InvalidProxy as e:
        raise ProxyError(str(e)) from e

    except BotProtectionDetected as e:
        raise BotDetection(str(e)) from e

    except UnknownError as e:
        raise UnknownNetworkError(str(e)) from e


class Account(Helper):
    def __init__(self, core: BaseCore, cookies: dict | None = cookies):
        super().__init__(core=core, video_constructor=Video)
        self.core = core
        self.cookies = cookies

        if not self.cookies:
            raise NoLoginCookies("""
You have not provided any login cookies. Please set them in the consts module like:

consts.cookies = {
session_token = <token>
session_token_auth = <token>
            }            
            """)

        assert isinstance(self.core.session, AsyncSession)
        self.core.session.cookies.update(cookies)
        self.core.session.headers.update(headers)
        self.logger = setup_logger(name="XVIDEOS API - [Account]", log_file=None, level=logging.ERROR)


    async def get_recommended_videos(self, pages: int = 2, videos_concurrency: int | None = None,
                                     pages_concurrency: int | None = None) -> AsyncGenerator[Video, None]:

        page_urls = [f"https://www.xvideos.com/history/{page}" for page in range(pages)]
        videos_concurrency = videos_concurrency or self.core.configuration.videos_concurrency
        pages_concurrency = pages_concurrency or self.core.configuration.pages_concurrency
        assert videos_concurrency and pages_concurrency

        async for video in self.iterator(target_page_urls=page_urls, video_link_extractor=extractor_account,
                                         max_video_concurrency=videos_concurrency,
                                         max_page_concurrency=pages_concurrency,
                                         page_request_method="POST"):

            yield await video.init()

    async def get_liked_videos(self, pages: int = 2, videos_concurrency: int | None = None,
                                     pages_concurrency: int | None = None) -> AsyncGenerator[Video, None]:

        page_urls = [f"https://www.xvideos.com/videos-i-like/{page}" for page in range(pages)]
        videos_concurrency = videos_concurrency or self.core.configuration.videos_concurrency
        pages_concurrency = pages_concurrency or self.core.configuration.pages_concurrency
        assert videos_concurrency and pages_concurrency
        async for video in self.iterator(target_page_urls=page_urls, video_link_extractor=extractor_account,
                                         max_video_concurrency=videos_concurrency,
                                         max_page_concurrency=pages_concurrency,
                                         page_request_method="POST"):

            yield await video.init()
    async def get_watch_later_videos(self, pages: int = 2, videos_concurrency: int | None = None,
                                     pages_concurrency: int | None = None) -> AsyncGenerator[Video, None]:

        page_urls = [f"https://www.xvideos.com/watch-later/{page}" for page in range(pages)]
        videos_concurrency = videos_concurrency or self.core.configuration.videos_concurrency
        pages_concurrency = pages_concurrency or self.core.configuration.pages_concurrency
        assert videos_concurrency and pages_concurrency
        async for video in self.iterator(target_page_urls=page_urls, video_link_extractor=extractor_account,
                                         max_video_concurrency=videos_concurrency,
                                         max_page_concurrency=pages_concurrency,
                                         page_request_method="POST"):

            yield await video.init()



class Video:
    def __init__(self, url, core: BaseCore, html_content=None):
        """
        :param url: (str) The URL of the video
        """
        self.core = core
        self.url = self.check_url(url)
        self.logger = setup_logger(name="XVIDEOS API - [Video]", log_file=None, level=logging.ERROR)
        self.html_content = html_content
        self._soup = None
        self.json_data = {}
        self.quality_url_map = None
        self.available_qualities = None

    async def init(self):
        if not self.html_content:
            self.html_content = await get_html_content(core=self.core, url=self.url)

        assert isinstance(self.html_content, str)
        self._soup = BeautifulSoup(self.html_content, parser)
        self.json_data = self.meta
        return self

    def enable_logging(self, log_file: str | None = None, level: int | None = None, log_ip: str | None = None, log_port: int | None = None):
        if not level:
            level = logging.DEBUG

        self.logger = setup_logger(name="XVIDEOS API - [Video]", log_file=log_file, level=level, http_ip=log_ip, http_port=log_port)

    @property
    def soup(self) -> BeautifulSoup:
        # lxml is much faster than the default parser
        if not self._soup:
            raise ValueError("You probably forgot to call init")

        return self._soup

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

    def _get_json_data(self) -> dict:
        data = {}
        for s in self.soup.select('script[type="application/ld+json"]'):
            if not s.string:
                continue
            try:
                data.update(json.loads(s.string))
            except Exception:
                continue
        return data

    @property
    def meta(self) -> dict:
        j = self._get_json_data()
        # Defensive access because JSON-LD varies
        return {
            "name": j.get("name"),
            "description": j.get("description"),
            "thumbnailUrl": (j.get("thumbnailUrl") or [None])[0] if isinstance(j.get("thumbnailUrl"), list) else j.get(
                "thumbnailUrl"),
            "uploadDate": j.get("uploadDate"),
            "contentUrl": j.get("contentUrl"),
        }

    async def get_segments(self, quality) -> list:
        """
        :param quality: (str, Quality) The video quality
        :return: (list) A list of segments (the .ts files)
        """
        segments = await self.core.get_segments(quality=quality, m3u8_url_master=self.m3u8_base_url)
        return segments

    async def download(self, quality, path="./", callback: callback_hint = None, no_title=False, remux: bool = False,
                 callback_remux=None, start_segment: int = 0, stop_event: threading.Event | None = None,
                 segment_state_path: str | None = None, segment_dir: str | None = None,
                 return_report: bool = False, cleanup_on_stop: bool = True, keep_segment_dir: bool = False
                 ) -> bool | DownloadReport:
        """
        :param callback:
        :param quality:
        :param path:
        :param no_title:
        :param remux:
        :param callback_remux:
        :param start_segment:
        :param stop_event:
        :param segment_state_path:
        :param segment_dir:
        :param return_report:
        :param cleanup_on_stop:
        :param keep_segment_dir:
        :return:
        """
        if not no_title:
            path = os.path.join(path, f"{self.title}.mp4")

        try:
            return await self.core.download(video=self, quality=quality, path=path, callback=callback, remux=remux,
                                  callback_remux=callback_remux, start_segment=start_segment, stop_event=stop_event,
                                  segment_state_path=segment_state_path, segment_dir=segment_dir,
                                  return_report=return_report,
                                  cleanup_on_stop=cleanup_on_stop, keep_segment_dir=keep_segment_dir)

        except Exception: # I should improve this in the future
            error = traceback.format_exc()
            self.logger.warning(f"Video doesn't have an HLS stream. Exception: {error}")
            self.logger.warning("Using legacy downloading instead...")
            await self.core.legacy_download(path=path, callback=callback, url=self.cdn_url)
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
        return self.json_data["thumbnailUrl"]

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
    def __init__(self, url: str, core: BaseCore):
        super().__init__(core=core, video_constructor=Video)
        self.core = core
        self.logger = setup_logger(name="XVIDEOS API - [Channel]", log_file=None, level=logging.ERROR)
        if "/channels/" not in url and "profiles" not in url:
            self.logger.warning("/channels/ not in URL. Trying to fix manually. This CAN lead to more errors!")
            self.url = url.replace("xvideos.com/", "xvideos.com/channels/")
        else:
            self.url = url
        self.bs4_about_me = None
        self.data = None

    async def init(self):
        base_content = await get_html_content(url=f"{self.url}/videos/best/0", core=self.core)
        about_me_html = await get_html_content(url=f"{self.url}#_tabAboutMe", core=self.core)

        assert isinstance(about_me_html, str)
        assert isinstance(base_content, str)
        self.bs4_about_me = BeautifulSoup(about_me_html, parser)
        self.data = json.loads(base_content)
        return self

    def enable_logging(self, log_file: str | None = None, level: int | None = None, log_ip: str | None = None,
                       log_port: int | None = None):
        if not level:
            level = logging.DEBUG
        self.logger = setup_logger(name="XVIDEOS API - [Channel]", log_file=log_file, level=level, http_ip=log_ip, http_port=log_port)

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

    async def videos(self, pages: int = 0, videos_concurrency: int | None = None, pages_concurrency: int | None = None) -> AsyncGenerator[Video, None]:
        if pages > self.total_pages:
            self.logger.warning(f"You want to fetch: {self.total_pages} pages but only: {self.total_pages} are available. Reducing!")
            pages = self.total_pages

        if pages == 0:
            pages = self.total_pages

        page_urls = [f"{self.url}/videos/best/{i}" for i in range(pages)] # Don't exceed total available pages
        self.logger.debug(f"Processing: {len(page_urls)} pages...")
        videos_concurrency = videos_concurrency or self.core.configuration.videos_concurrency
        pages_concurrency = pages_concurrency or self.core.configuration.pages_concurrency
        assert videos_concurrency and pages_concurrency
        async for video in self.iterator(target_page_urls=page_urls, video_link_extractor=extractor_account,
                                         max_video_concurrency=videos_concurrency,
                                         max_page_concurrency=pages_concurrency):

            yield await video.init()

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
    def __init__(self, core: BaseCore, url: str):
        super().__init__(core=core, video_constructor=Video)
        self.core = core
        self.url = self.check_url(url)
        self.bs4_about_me = None
        self.data = None
        self.logger = setup_logger(name="XVIDEOS API - [Pornstar]", log_file=None, level=logging.ERROR)
        
    async def init(self):
        base_content = await get_html_content(url=f"{self.url}/videos/best/0", core=self.core)
        about_me_html = await get_html_content(url=f"{self.url}#_tabAboutMe", core=self.core)

        assert isinstance(about_me_html, str)
        assert isinstance(base_content, str)
        self.bs4_about_me = BeautifulSoup(about_me_html, parser)
        self.data = json.loads(base_content)
        return self

    def enable_logging(self, log_file: str | None = None, level: int | None = None, log_ip: str | None = None,
                       log_port: int | None = None):
        if not level:
            level = logging.DEBUG
        self.logger = setup_logger(name="XVIDEOS API - [Pornstar]", log_file=log_file, level=level, http_ip=log_ip, http_port=log_port)

    def check_url(self, url):
        if ("/pornstars" not in url) and ("/model" not in url):
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

    async def videos(self, pages: int = 0, videos_concurrency: int | None = None, pages_concurrency: int | None = None) -> AsyncGenerator[Video, None]:
        if pages > self.total_pages:
            self.logger.warning(
                f"You want to fetch: {self.total_pages} pages but only: {self.total_pages} are available. Reducing!")
            pages = self.total_pages

        if pages == 0:
            pages = self.total_pages

        page_urls = [f"{self.url}/videos/best/{i}" for i in range(pages)]  # Don't exceed total available pages
        self.logger.debug(f"Processing: {len(page_urls)} pages...")
        videos_concurrency = videos_concurrency or self.core.configuration.videos_concurrency
        pages_concurrency = pages_concurrency or self.core.configuration.pages_concurrency
        assert videos_concurrency and pages_concurrency

        async for video in self.iterator(target_page_urls=page_urls, video_link_extractor=extractor_account,
                                         max_video_concurrency=videos_concurrency,
                                         max_page_concurrency=pages_concurrency):

            yield await video.init()


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
    def __init__(self, core: BaseCore = BaseCore()):
        super().__init__(core, video_constructor=Video)
        self.core = core
        self.core.initialize_session()
        self.logger = setup_logger(name="XVIDEOS API - [Client]", log_file=None, level=logging.ERROR)

    def enable_logging(self, log_file: str | None = None, level: int | None = None, log_ip: str | None = None,
                       log_port: int | None = None):
        if not level:
            level = logging.DEBUG
        self.logger = setup_logger(name="XVIDEOS API - [Client]", log_file=log_file, level=level, http_ip=log_ip, http_port=log_port)

    async def get_video(self, url: str) -> Video:
        """
        :param url: (str) The video URL
        :return: (Video) The video object
        """
        video = Video(url, core=self.core)
        return await video.init()

    async def search(self, query: str, sorting_sort: str | Sort = Sort.Sort_relevance,
               sorting_date: str | SortDate = SortDate.Sort_all,
               sorting_time: str | SortVideoTime = SortVideoTime.Sort_all,
               sort_quality: str | SortQuality = SortQuality.Sort_all,
               pages: int = 2, videos_concurrency: int | None = None,
               pages_concurrency: int | None = None) -> AsyncGenerator[Video, None]:

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
        videos_concurrency = videos_concurrency or self.core.configuration.videos_concurrency
        pages_concurrency = pages_concurrency or self.core.configuration.pages_concurrency
        assert videos_concurrency and pages_concurrency
        async for video in self.iterator(target_page_urls=page_urls, video_link_extractor=extractor_account,
                                         max_video_concurrency=videos_concurrency,
                                         max_page_concurrency=pages_concurrency):

            yield await video.init()

    async def get_playlist(self, url: str, pages: int = 2, videos_concurrency: int | None = None,
                     pages_concurrency: int | None = None) -> AsyncGenerator[Video, None]:
        page_urls = [f"{url}/{page}" for page in range(pages)]
        videos_concurrency = videos_concurrency or self.core.configuration.videos_concurrency
        pages_concurrency = pages_concurrency or self.core.configuration.pages_concurrency
        assert videos_concurrency and pages_concurrency

        async for video in self.iterator(target_page_urls=page_urls, video_link_extractor=extractor_account,
                                         max_video_concurrency=videos_concurrency,
                                         max_page_concurrency=pages_concurrency):

            yield await video.init()

    async def get_pornstar(self, url) -> Pornstar:
        pornstar = Pornstar(core=self.core, url=url)
        return await pornstar.init()

    async def get_channel(self, url) -> Channel:
        channel = Channel(url, core=self.core)
        return await channel.init()

    def get_account(self) -> Account:
        account = Account(core=self.core)
        return account


async def run_main():
    parser = argparse.ArgumentParser(description="API Command Line Interface")
    parser.add_argument("--download", metavar="URL (str)", type=str, help="URL to download from")
    parser.add_argument("--quality", metavar="best,half,worst", type=str, help="The video quality (best,half,worst)",
                        required=True)
    parser.add_argument("--file", metavar="Source to .txt file", type=str,
                        help="(Optional) Specify a file with URLs (separated with new lines)")
    parser.add_argument("--output", metavar="Output directory", type=str, help="The output path (with filename)",
                        required=True)
    parser.add_argument("--no-title", metavar="True,False", type=str,
                        help="Whether to apply video title automatically to output path or not", required=True)

    args = parser.parse_args()
    no_title = str_to_bool(args.no_title)
    if args.download:
        client = Client()
        video = await client.get_video(args.download)
        await video.download(quality=args.quality, path=args.output, no_title=no_title)

    if args.file:
        videos = []
        client = Client()

        with open(args.file, "r") as file:
            content = file.read().splitlines()

        for url in content:
            videos.append(await client.get_video(url))

        for video in videos:
            await video.download(quality=args.quality, path=args.output, no_title=no_title)


if __name__ == "__main__":
    asyncio.run(run_main())