class InvalidUrl(Exception):
    def __init__(self, msg):
        self.msg = msg


class VideoUnavailable(Exception):
    def __init__(self, msg):
        self.msg = msg


class InvalidPornstar(Exception):
    def __init__(self, msg):
        self.msg = msg
