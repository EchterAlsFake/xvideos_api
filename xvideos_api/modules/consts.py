import re
import json

from bs4 import SoupStrainer, BeautifulSoup
from urllib.parse import urljoin

REGEX_VIDEO_CHECK_URL = re.compile(r'(.*?)xvideos.com/video(.*?)')
REGEX_VIDEO_M3U8 = re.compile(r"html5player\.setVideoHLS\('([^']+)'\);")
REGEX_IFRAME = re.compile(r'video-embed" type="text" readonly value="(.*?)" class="form-control"')
REGEX_SEARCH_SCRAPE_VIDEOS = re.compile(r'none;"><a href="(.*?)">', re.DOTALL)

headers = {
    "Referer": "https://xvideos.com/",
}


def extractor_json(html: str):
    """
    Extracts the video URLs from a HTML. This function needs to be given to the iterator function
    in the Helper class. See BaseCore (eaf_base_api)

    This function is for JSON type returns e.g., /best/1 URL types. This does NOT work for HTML.
    See extractor below.

    """
    data = json.loads(html)
    video_urls = []
    for u in (v.get("u") for v in data.get("videos", [])):
        if not u:
            continue
        parts = str(u).split("/")
        if len(parts) >= 6:
            vid = parts[4]
            slug = parts[5]
            video_urls.append(f"https://www.xvideos.com/video.{vid}/{slug}")


def extractor_html(html: str) -> list:
    strainer = SoupStrainer('div', class_='thumb')  # parse only these nodes
    soup = BeautifulSoup(html, 'lxml', parse_only=strainer)
    out = []
    for div in soup.find_all('div', class_='thumb'):
        a_tag = div.find('a', href=True)
        if a_tag and a_tag['href']:
            out.append(a_tag['href'])

    video_urls = [urljoin("https://www.xvideos.com", u) for u in out if "video." in u]
    return video_urls
