import re
import json

from typing import List
from urllib.parse import urljoin
from bs4 import SoupStrainer, BeautifulSoup

try:
    import lxml
    parser = "lxml"

except (ModuleNotFoundError, ImportError):
    parser = "html.parser"


REGEX_VIDEO_CHECK_URL = re.compile(r'(.*?)xvideos.com/video(.*?)')
REGEX_VIDEO_M3U8 = re.compile(r"html5player\.setVideoHLS\('([^']+)'\);")
REGEX_IFRAME = re.compile(r'video-embed" type="text" readonly value="(.*?)" class="form-control"')
REGEX_SEARCH_SCRAPE_VIDEOS = re.compile(r'none;"><a href="(.*?)">', re.DOTALL)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.xvideos.com/",
    "X-Requested-With": "XMLHttpRequest", # For Account stuff
    "Connection": "keep-alive",
}

cookies = None


# Please submit your login cookies here like:

"""
cookies = {
session_token = <token>
session_token_auth = <token>
}
"""

def extractor_json(html: str) -> List[str]:
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

    return video_urls


def extractor_html(html: str) -> List[str]:
    strainer = SoupStrainer('div', class_='thumb')  # parse only these nodes
    soup = BeautifulSoup(html, parser, parse_only=strainer)
    out = []
    for div in soup.find_all('div', class_='thumb'):
        a_tag = div.find('a', href=True)
        if a_tag and a_tag['href']:
            out.append(a_tag['href'])

    video_urls = [urljoin("https://www.xvideos.com", u) for u in out if "video." in u]
    return video_urls


def extractor_account(html: str) -> List[str]:
    video_urls = []
    # Using 'html.parser' explicitly to avoid undefined variable errors
    soup = BeautifulSoup(html, parser)

    # Target the container div using its distinct classes instead of the duplicate ID
    divs = soup.find_all("div", class_="frame-block")

    for stuff in divs:
        # Safely find the title paragraph
        title_p = stuff.find("p", class_="title")
        if title_p:
            a_tag = title_p.find("a")
            if a_tag and a_tag.get("href"):
                video_url = a_tag.get("href")
                video_urls.append(f"https://www.xvideos.com{video_url}")

    return video_urls