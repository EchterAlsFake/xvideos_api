# 1.0

- Initial Commit

# 1.1

- implemented searching
- implemented search filters
- unit tests for searching
- updated documentation

# 1.2
- code optimization
- added embed url to video objects
- added legacy downloading for low-quality videos

# 1.3
- implemented the Pornstar object

# 1.4
- using infinite page generating instead of static one (for Porn Fetch)

# 1.4.1
- updating to the new eaf_base_api requirements

# 1.5
- removed json5 requirement
- fixed tests
- added VideoUnavailable exception
- code refactoring and type hinting

# 1.5.1
- switched to httpx
- removed lxml and requests from project dependencies

# 1.5.7
- Channel support
- Added Channel and Pornstar metadata from the #about_me tab
- Switched project to Beautifulsoup from regular expressions
- "author" from video object will now reference the actual channel object instead of a name
- "pornstar" objects from videos will now reference the actual Pornstar objects instead of names
- Enabled network logging
