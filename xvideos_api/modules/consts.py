import re

REGEX_VIDEO_CHECK_URL = re.compile(r'(.*?)xvideos.com/video(.*?)')
REGEX_VIDEO_M3U8 = re.compile(r"html5player\.setVideoHLS\('([^']+)'\);")
REGEX_IFRAME = re.compile(r'video-embed" type="text" readonly value="(.*?)" class="form-control"')
REGEX_SEARCH_SCRAPE_VIDEOS = re.compile(r'none;"><a href="(.*?)">', re.DOTALL)

headers = {
    "Referer": "https://xvideos.com/",
}