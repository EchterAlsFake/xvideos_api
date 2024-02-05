import re

REGEX_VIDEO_CHECK_URL = re.compile(r'https://www.xvideos.com/video(.*?)')
REGEX_VIDEO_M3U8 = re.compile(r"html5player\.setVideoHLS\('([^']+)'\);")
REGEX_VIDEO_TAGS = re.compile(r'href="/tags/(.*?)" class="is-keyword', re.DOTALL)
REGEX_VIDEO_VIEWS = re.compile(r'<strong class="mobile-hide">(.*?)</strong>')
REGEX_VIDEO_RATING_LIKES = re.compile(r'<span class="rating-good-nbr">(.*?)</span>')
REGEX_VIDEO_RATING_DISLIKES = re.compile(r'<span class="rating-bad-nbr">(.*?)</span>')
REGEX_VIDEO_RATING_VOTES = re.compile(r'<span class="rating-total-txt">(.*?)</span>')
REGEX_VIDEO_COMMENT_COUNT = re.compile(r'<span class="badge">(.*?)</span>')
REGEX_VIDEO_UPLOADER = re.compile(r'<a href="/channels/(.*?)" class="btn btn-default label main')
REGEX_VIDEO_LENGTH = re.compile(r'<span class="duration">(.*?)</span>')
REGEX_VIDEO_PORNSTARS = re.compile(r'a href="/models/(.*?)" class=')

REGEX_SEARCH_SCRAPE_VIDEOS = re.compile(r'none;"><a href="(.*?)">', re.DOTALL)
