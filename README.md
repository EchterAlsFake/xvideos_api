<h1 align="center">XVIDEOS API</h1> 

<div align="center">
    <a href="https://pepy.tech/project/xvideos_api"><img src="https://static.pepy.tech/badge/xvideos_api" alt="Downloads"></a>
    <a href="https://pepy.tech/project/xvideos_api-async"><img src="https://static.pepy.tech/badge/xvideos_api-async" alt="Downloads"></a> <pan style="font-size: 20px">(Async)</pan>
    <a href="https://github.com/EchterAlsFake/xvideos_api/workflows/"><img src="https://github.com/EchterAlsFake/xvideos_api/workflows/CodeQL/badge.svg" alt="CodeQL Analysis"/></a>
    <a href="https://github.com/EchterAlsFake/xvideos_api/actions/workflows/sync-tests.yml"><img src="https://github.com/EchterAlsFake/xvideos_api/actions/workflows/sync-tests.yml/badge.svg" alt="Sync API Tests"/></a>
    <a href="https://github.com/EchterAlsFake/xvideos_api/actions/workflows/async-tests.yml"><img src="https://github.com/EchterAlsFake/xvideos_api/actions/workflows/async-tests.yml/badge.svg?branch=async" alt="Async Branch API Tests"></a>
</div>

# Description
XVideos API is an API for xvideos.com. It allows you to fetch information from videos using regexes and requests.

# Disclaimer
> [!IMPORTANT] 
> XVideos API is in violation to the ToS of xvideos.com!
> If you are the website owner of xvideos.com, contact me at my E-Mail, and I'll take this repository immediately offline.
> EchterAlsFake@proton.me

# Quickstart

### Have a look at the [Documentation](https://github.com/EchterAlsFake/API_Docs/blob/master/Porn_APIs/XVideos.md) for more details
- Install the library with `pip install xvideos_api`


```python
from xvideos_api import Client
# Initialize a Client object
client = Client()

# Fetch a video
video_object = client.get_video("<insert_url_here>")

# Information from Video objects
print(video_object.title)
print(video_object.likes)
# Download the video

video_object.download(downloader="threaded", quality="best", path="your_output_path + filename")

# SEE DOCUMENTATION FOR MORE
```

> [!NOTE]
> XVideos API can also be used from the command line. Do: xvideos_api -h to see the options
# Changelog
See [Changelog](https://github.com/EchterAlsFake/xvideos_api/blob/master/README/Changelog.md) for more details.

# Support (Donations)
I am developing all my projects entirely for free. I do that because I have fun and I don't want
to charge 30€ like other people do.

However, if you find my work useful, please consider donating something. A tiny amount such as 1€
means a lot to me.

Paypal: https://paypal.me/EchterAlsFake
<br>XMR (Monero): `46xL2reuanxZgFxXBBaoagiEJK9c7bL7aiwKNR15neyX2wUsX2QVzkeRMVG2Cro44qLUNYvsP1BQa12KPbNat2ML41nyEeq`


# Contribution
Do you see any issues or having some feature requests? Simply open an Issue or talk
in the discussions.

Pull requests are also welcome.

# License
Licensed under the LGPLv3 License
<br>Copyright (C) 2023–2025 Johannes Habel
