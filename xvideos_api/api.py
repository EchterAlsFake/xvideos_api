from __future__ import annotations
import copy
import os
import re
import math
import json
import html
import asyncio
import argparse
import logging
from typing import AsyncGenerator, ClassVar
from dataclasses import dataclass
from selectolax.lexbor import LexborHTMLParser
from curl_cffi.requests import AsyncSession
from base_api.modules.type_hints import DownloadReport
from base_api.modules.config import IteratorConfig
from base_api.modules.static_functions import str_to_bool
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from base_api import (
    BaseCore,
    BaseMedia,
    DownloadConfigHLS,
    ErrorAction,
    ErrorMode,
    Helper,
    MediaLoadError,
    MediaLoadErrors,
    RetryPolicy,
    ScrapeErrorContext,
    ScrapeResult,
    media_field,
    make_iterator_config,
    is_resource_gone,
    default_on_error,
    scrape_stream,
)
from base_api.modules.errors import (
    BotProtectionDetected,
    HTTPStatusError,
    InvalidProxy,
    NetworkRequestError,
    ResourceGone,
    UnknownError,
)

from xvideos_api.modules.errors import (NotFound, NetworkError, UnknownNetworkError, BotDetection,
                                        ProxyError, DownloadFailed, NoLoginCookies)
from xvideos_api.modules.consts import (cookies, headers, extractor_account, REGEX_VIDEO_M3U8, REGEX_IFRAME)
from xvideos_api.modules.sorting import Sort, SortVideoTime, SortQuality, SortDate


logger = logging.getLogger("XVideos API")
logger.addHandler(logging.NullHandler())


HELPER_RETRY = RetryPolicy(max_attempts=4, base_delay=0.5, max_delay=8.0)

_is_resource_gone = is_resource_gone
on_error = default_on_error


async def get_html_content(core: BaseCore, url: str) -> str:
    try:
        logger.debug(f"Fetching HTML content for URL: {url}")
        return await core.fetch_text(url)

    except HTTPStatusError as e:
        if e.status_code == 404:
            raise NotFound(f"Server returned 404 for: {url}") from e
        raise

    except NetworkRequestError as e:
        raise NetworkError(str(e)) from e

    except InvalidProxy as e:
        raise ProxyError(str(e)) from e

    except BotProtectionDetected as e:
        raise BotDetection(str(e)) from e

    except UnknownError as e:
        raise UnknownNetworkError(str(e)) from e


class Account:
    def __init__(self, core: BaseCore, cookies: dict | None = cookies):
        self.core = core
        self.cookies = cookies
        self.helper = Helper(core=self.core, constructor=Video)

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


    def get_recommended_videos(
        self,
        pages: int = 2,
        iterator_config: IteratorConfig | None = None,
    ) -> AsyncGenerator[ScrapeResult[Video], None]:

        page_urls = [f"https://www.xvideos.com/history/{page}" for page in range(pages)]
        if iterator_config is None:
            iterator_config = make_iterator_config(page_request_method="POST")

        return scrape_stream(
            core=self.core,
            constructor=Video,
            target_page_urls=page_urls,
            item_extractor=extractor_account,
            iterator_config=iterator_config,
        )

    def get_liked_videos(
        self,
        pages: int = 2,
        iterator_config: IteratorConfig | None = None,
    ) -> AsyncGenerator[ScrapeResult[Video], None]:

        page_urls = [f"https://www.xvideos.com/videos-i-like/{page}" for page in range(pages)]
        if iterator_config is None:
            iterator_config = make_iterator_config(page_request_method="POST")

        return scrape_stream(
            core=self.core,
            constructor=Video,
            target_page_urls=page_urls,
            item_extractor=extractor_account,
            iterator_config=iterator_config,
        )

    def get_watch_later_videos(
        self,
        pages: int = 2,
        iterator_config: IteratorConfig | None = None,
    ) -> AsyncGenerator[ScrapeResult[Video], None]:

        page_urls = [f"https://www.xvideos.com/watch-later/{page}" for page in range(pages)]
        if iterator_config is None:
            iterator_config = make_iterator_config(page_request_method="POST")

        return scrape_stream(
            core=self.core,
            constructor=Video,
            target_page_urls=page_urls,
            item_extractor=extractor_account,
            iterator_config=iterator_config,
        )


@dataclass(slots=True, kw_only=True)
class Video(BaseMedia):
    url: str
    core: BaseCore
    title: str | None = media_field("html")
    description: str | None = media_field("html")
    thumbnail_url: str | None = media_field("html")
    preview_video_url: str | None = media_field("html")
    publish_date: str | None = media_field("html")
    content_url: str | None = media_field("html")
    tags: list | None = media_field("html")
    views: str | None = media_field("html")
    likes: str | None = media_field("html")
    dislikes: str | None = media_field("html")
    rating_votes: str | None = media_field("html")
    comment_count: str | None = media_field("html")
    author_link: str | None = media_field("html")
    length: str | None = media_field("html")
    pornstars_urls: list | None = media_field("html")
    embed_url: str | None = media_field("html")
    cdn_url: str | None = None
    m3u8_base_url: str | None = media_field("html")

    # Optional
    video_id: str | None = None

    loader_methods: ClassVar[dict[str, str]] = {"html": "_load_html"}

    async def _load_html(self) -> dict[str, object]:
        html_content = await get_html_content(core=self.core, url=self.url)
        return await asyncio.to_thread(self._extract_html, html_content)

    @staticmethod
    def _extract_html(html_content: str) -> dict:
        parser = LexborHTMLParser(html_content)

        data = {}
        for s in parser.css('script[type="application/ld+json"]'):
            if not s.text():
                continue
            try:
                data.update(json.loads(s.text()))
            except Exception:
                continue

        title = html.unescape(data.get("name"))
        description = data.get("description")
        thumbnail_url = (data.get("thumbnailUrl") or [None])[0] if isinstance(data.get("thumbnailUrl"), list) else data.get("thumbnailUrl")
        publish_date = data.get("uploadDate")
        content_url = data.get("contentUrl")
        m3u8_base_url = REGEX_VIDEO_M3U8.search(html_content).group(1)
        thumb = html.unescape(data.get("thumbnailUrl"))[0]
        base_url = re.sub(r'/thumbs(169)?(xnxx)?(l*|poster)/', '/videopreview/', thumb[:thumb.rfind("/")])
        suffix = re.search(r'-(\d+)', base_url)
        base_url = re.sub(r'-(\d+)', '', base_url) if suffix else base_url
        preview_video_url = f"{base_url}_169{suffix.group(0) if suffix else ''}.mp4"
        elements = parser.css("a.is-keyword.btn.btn-default")
        tags = [tag.text() for tag in elements]
        views = parser.css_first("span.icon-f.icf-eye").next.text(strip=True)
        likes = parser.css_first("span.rating-good-nbr").text(strip=True)
        dislikes = parser.css_first("span.rating-bad-nbr").text(strip=True)
        rating_votes = parser.css_first("span.rating-total-txt").text(strip=True)
        comment_count = parser.css_first("button.comments.tab-button").next.next.text(strip=True)
        embed_url = REGEX_IFRAME.search(html.unescape(html_content)).group(1)
        length = parser.css_first("span.duration").text(strip=True)

        try:
            link = parser.css_first("li.main-uploader").css_first('a').attributes.get("href")
            assert isinstance(link, str)
            if not link.startswith("/profiles"):
                author_link = f"https://xvideos.com/channels"

            else:
                author_link = f"https://xvideos.com{link}"

        except AttributeError:
            author_link = None


        _pornstars = parser.css('li.model')
        pornstars = []
        for pornstar in _pornstars:
            pornstars.append(f"https://xvideos.com{pornstar.next.attributes.get('href')}")

        return {
            "title": title,
            "description": description,
            "thumbnail_url": thumbnail_url,
            "publish_date": publish_date,
            "content_url": content_url,
            "m3u8_base_url": m3u8_base_url,
            "preview_video_url": preview_video_url,
            "tags": tags,
            "views": views,
            "likes": likes,
            "dislikes": dislikes,
            "rating_votes": rating_votes,
            "comment_count": comment_count,
            "embed_url": embed_url,
            "length": length,
            "author_link": author_link,
            "pornstars_urls": pornstars,
        }

    async def download(self, configuration: DownloadConfigHLS) -> bool | DownloadReport:
        """
        :param configuration:
        :return:
        """
        await self.load_fields("title", "m3u8_base_url")
        config = copy.deepcopy(configuration)
        if not config.no_title:
            config.path = os.path.join(config.path, f"{self.title}.mp4")

        config.m3u8_base_url = self.m3u8_base_url

        try:
            logger.info(f"Downloading video: {self.title}")
            return await self.core.download(configuration=config)

        except Exception as e: 
            logger.error(f"Failed to download video {self.title}: {e}")
            raise DownloadFailed(str(e))

    @property
    async def get_author(self, load_html: bool = True) -> Channel | None:
        url = await self.get_field("author_link")

        if url:
            channel = Channel(url=url, core=self.core)
            if load_html:
                await channel.load_sources("html")
            return channel

        return None

    @property
    async def get_pornstars(self, load_html: bool = True) -> AsyncGenerator[Pornstar, None]:
        pornstars_urls = await self.get_field("pornstars_urls")
        for url in pornstars_urls:
            star = Pornstar(url=url, core=self.core)
            if load_html:
                await star.load_sources("html")
            yield star



@dataclass(kw_only=True, slots=True)
class BaseChannelPornstar(BaseMedia):
    url: str
    core: BaseCore
    name: str | None = media_field("html")
    thumbnail_url: str | None = media_field("html")
    total_videos: int | None = media_field("html")
    per_page: int | None = media_field("html")
    total_pages: int | None = media_field("html")
    profile_hits: str | None = media_field("html")
    subscribers: str | None = media_field("html")
    total_videos_views: str | None = media_field("html")
    signed_up: str | None = media_field("html")
    last_activity: str | None = media_field("html")
    worked_for_with_links: list | None = media_field("html")

    loader_methods: ClassVar[dict[str, str]] = {"html": "_load_html"}

    async def _load_html(self) -> dict[str, object]:
        self._sanitize_url()

        json_data = asyncio.create_task(get_html_content(url=f"{self.url}/videos/best/0", core=self.core))
        html_content = asyncio.create_task(get_html_content(url=f"{self.url}#_tabAboutMe", core=self.core))

        json_data, html_content = await asyncio.gather(json_data, html_content)

        return await asyncio.to_thread(
            self._extract_data,
            html_content=html_content,
            base_content=json_data,
        )

    def _sanitize_url(self):
        ...


    @staticmethod
    def _extract_data(html_content: str, base_content: str):
        json_data = json.loads(base_content)
        parser = LexborHTMLParser(html_content)

        name = parser.css_first('h2 strong.text-danger').text()
        thumbnail_url = parser.css_first('div.profile-pic img').attributes.get('src')
        total_videos = int(json_data["nb_videos"])
        per_page = int(json_data["nb_per_page"])
        total_pages = math.ceil(total_videos / per_page)
        profile_hits = parser.css_first('#pinfo-profile-hits span').text(strip=True)
        subscribers = parser.css_first('#pinfo-subscribers span').text(strip=True)
        try:
            total_video_views = parser.css_first('#pinfo-videos-views span').text(strip=True)

        except:
            paragraphs = parser.css('#pfinfo-col-col1 p')
            # Assuming 'Total Videoaufrufe' is always the 5th <p> tag (index 4)
            if len(paragraphs) > 4:
                total_video_views = paragraphs[4].css_first('span').text(strip=True)

        signed_up = parser.css_first('#pinfo-signedup span').text(strip=True)
        try:
            last_activity = parser.css_first('#pinfo-lastactivity span').text(strip=True)
        except:
            last_activity = None # Can be None sometimes, because it's not always available on the page lol

        names = parser.css('#pinfo-workedfor a')
        worked_for_with_links = [a.attributes.get('href') for a in names if a.attributes.get('href')]

        return {
            "name": name,
            "thumbnail_url": thumbnail_url,
            "total_videos": total_videos,
            "per_page": per_page,
            "total_pages": total_pages,
            "profile_hits": profile_hits,
            "subscribers": subscribers,
            "total_videos_views": total_video_views,
            "signed_up": signed_up,
            "last_activity": last_activity,
            "worked_for_with_links": worked_for_with_links,
        }

    async def worked_for_with(self, load_html: bool = True) -> list[Channel]:
        await self.load_fields("worked_for_with_links")
        links_corrected = []

        for link in self.worked_for_with_links:
            if not "profile" in link:
                links_corrected.append(f"https://xvideos.com/channels{link}")

            else:
                links_corrected.append(f"https://xvideos.com{link}")

        channels = [Channel(core=self.core, url=url) for url in links_corrected]
        if load_html:
            await asyncio.gather(*(channel.load_sources("html") for channel in channels))
        return channels

    async def videos(
        self,
        pages: int = 0,
        iterator_config: IteratorConfig | None = None,
    ) -> AsyncGenerator[ScrapeResult[Video], None]:
        total_pages = await self.get_field("total_pages")
        if pages > total_pages:
            pages = total_pages

        if pages == 0:
            pages = total_pages
        url = self.url
        page_urls = [f"{url}/videos/best/{i}" for i in range(pages)] # Don't exceed total available pages
        if iterator_config is None:
            iterator_config = make_iterator_config()

        stream = scrape_stream(
            core=self.core,
            constructor=Video,
            target_page_urls=page_urls,
            item_extractor=extractor_account,
            iterator_config=iterator_config,
        )
        async for scrape_result in stream:
            yield scrape_result


@dataclass(kw_only=True, slots=True)
class Channel(BaseChannelPornstar):
    url: str
    core: BaseCore

    def _sanitize_url(self):
        if "/channels/" not in self.url and "profiles" not in self.url:
            self.url = self.url.replace("xvideos.com/", "xvideos.com/channels/")


@dataclass(kw_only=True, slots=True)
class Pornstar(BaseChannelPornstar):
    gender: str | None = media_field("html")
    age: str | None = media_field("html")
    video_tags: str | None = media_field("html")

    @staticmethod
    def _extract_data(html_content: str, base_content: str) -> dict:
        data = BaseChannelPornstar._extract_data(html_content, base_content)
        parser = LexborHTMLParser(html_content)
        data["gender"] = parser.css_first('#pinfo-sex span').text(strip=True)
        try:
            data["age"] = parser.css_first('#pinfo-age span').text(strip=True)
        except:
            data["age"] = None

        data["video_tags"] = parser.css_first('#pinfo-video-tags span').text(strip=True)
        return data


class Client:
    def __init__(self, core: BaseCore | None = None):
        if core is None:
            core = BaseCore()
        self.core = core
        self.account = None
        self.core.initialize_session()
        self.helper = Helper(core=self.core, constructor=Video)
        logger.info("Client initialized")

    async def get_video(self, url: str, load_html: bool = True) -> Video:
        """
        :param url: (str) The video URL
        :param load_html: (bool) Whether or not to load the html page
        :return: (Video) The video object
        """
        video = Video(url=url, core=self.core)
        if load_html:
            await video.load_sources("html")
        return video

    def search(self, query: str, sorting_sort: str | Sort = Sort.Sort_relevance,
               sorting_date: str | SortDate = SortDate.Sort_all,
               sorting_time: str | SortVideoTime = SortVideoTime.Sort_all,
               sort_quality: str | SortQuality = SortQuality.Sort_all,
               pages: int | str = "all",
               iterator_config: IteratorConfig | None = None,
                      ) -> AsyncGenerator[ScrapeResult[Video], None]:


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

        page_urls = [] # Empty page urls will lead to automatic iteration

        if isinstance(pages, int):
            page_urls = [f"{url}&p={p}" for p in range(pages)]

        if iterator_config is None:
            iterator_config = make_iterator_config()

        return scrape_stream(
            core=self.core,
            constructor=Video,
            target_page_urls=page_urls,
            item_extractor=extractor_account,
            iterator_config=iterator_config,
        )

    def get_playlist(
        self,
        url: str,
        pages: int = 2,
        iterator_config: IteratorConfig | None = None,
    ) -> AsyncGenerator[ScrapeResult[Video], None]:
        page_urls = [f"{url}/{page}" for page in range(pages)]
        if iterator_config is None:
            iterator_config = make_iterator_config()

        return scrape_stream(
            core=self.core,
            constructor=Video,
            target_page_urls=page_urls,
            item_extractor=extractor_account,
            iterator_config=iterator_config,
        )

    async def get_pornstar(self, url: str, load_html: bool = True) -> Pornstar:
        pornstar = Pornstar(core=self.core, url=url)
        if load_html:
            await pornstar.load_sources("html")
        return pornstar

    async def get_channel(self, url: str, load_html: bool = True) -> Channel:
        channel = Channel(url=url, core=self.core)
        if load_html:
            await channel.load_sources("html")
        return channel

    def get_account(self, cookies: dict | None = None) -> Account:
        if cookies:
            self.account = Account(core=self.core, cookies=cookies)
        else:
            self.account = Account(core=self.core)

        return self.account


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="XVideos API Command Line Interface")
    parser.add_argument("--download", metavar="URL", type=str, help="URL to download from")
    parser.add_argument("--quality", metavar="best|half|worst", type=str, default="best", help="The video quality (best, half, worst)")
    parser.add_argument("--file", metavar="FILE", type=str, help="(Optional) Specify a file with URLs (separated with new lines)")
    parser.add_argument("--output", metavar="DIR", type=str, required=True, help="The output path (with filename or directory)")
    parser.add_argument("--no-title", metavar="True,False", type=str, nargs="?", const="True", default="False",
                        help="Whether to apply video title automatically to output path or not")
    return parser


async def run_main(args_list: list[str] | None = None):
    parser = create_parser()
    args = parser.parse_args(args_list)
    no_title = str_to_bool(args.no_title) if isinstance(args.no_title, str) else bool(args.no_title)
    config = DownloadConfigHLS(
        quality=args.quality,
        path=args.output,
        no_title=no_title
    )

    urls: list[str] = []
    if args.download:
        urls.append(args.download)
    if args.file:
        with open(args.file, "r") as file:
            urls.extend([line.strip() for line in file.readlines() if line.strip()])

    if not urls:
        parser.print_help()
        return

    client = Client()
    for url in urls:
        print(f"Fetching video information for: {url}")
        try:
            video = await client.get_video(url, load_html=True)
            title = getattr(video, "title", None) or url
            print(f"Starting download for: {title}")
            await video.download(configuration=config)
            print(f"Download complete: {title}")
        except Exception as e:
            print(f"Error downloading {url}: {e}")


def main():
    try:
        asyncio.run(run_main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")


if __name__ == "__main__":
    main()

