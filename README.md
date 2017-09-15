MpegStreamSaver
===============
A simple tool to download, decrypt, and remux an Mpeg stream.

Disclaimer:  Requires a master.m3u file URL, and works on a specific subset of Mpeg stream - this does not implement the entire Mpeg stream spec.

Requirements
------------
- Python 3.6+
- pip/virtualenv
	- for the [cryptography](https://cryptography.io/en/latest/) library, to decrypt encrypted .ts files
- [ffmpeg](https://www.ffmpeg.org/) to form the final Mpeg file from .ts files

Usage
-----
1. Activate the virtualenv
2. Run `python3.6 main.py`
3. (Follow the directions)

Further Reading
---------------
- [The HTTP Live Streaming RFC](https://tools.ietf.org/html/draft-pantos-http-live-streaming-07)
- [Using ffmpeg to stream-copy (remux) an Mpeg stream from .ts files](https://askubuntu.com/questions/716424/how-to-convert-ts-file-into-main-stream-file-losslessly?answertab=votes#tab-top)
- [tempfiles with Python](https://docs.python.org/3/library/tempfile.html)
