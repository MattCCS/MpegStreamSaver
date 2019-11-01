"""
A tool to grab Mpeg Streams

See for details:
    https://tools.ietf.org/html/draft-pantos-http-live-streaming-07
"""

import argparse
import os
import pathlib
import re
import ssl
import subprocess
import tempfile
import concurrent.futures
import urllib.parse
import urllib.request

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


ROOT = pathlib.Path(__file__).absolute().parent
SAVES = ROOT / "saves"

MAX_PROCESSES = 4


class SymmetricEncryptionError(Exception):
    pass


def _decrypt(aes_key, aes_iv, ciphertext):
    """
    Decrypts the given ciphertext with the given
    key and initialization vector using
    AES-128 in Cipher Block Chaining (CBC) mode.
    + produces plaintext (private!)
    """
    backend = default_backend()

    try:
        # AES-128 in CBC mode
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_iv), backend=backend)
        decryptor = cipher.decryptor()

        return decryptor.update(ciphertext)

    except ValueError as err:
        raise SymmetricEncryptionError(err)


def test():
    with open("encryption.key", 'rb') as keyfile:
        key = keyfile.read()

    i = 0
    with open("index-v1-a1.m3u") as master:
        for line in master:
            if line.startswith("https://"):
                encrypted_data = unsafe_urlopen(line).read()

                i += 1
                print(f"Writing {i}")
                data = _decrypt(key, b"\x00" * 15 + bytes([i]), encrypted_data)

                with open(f"part{i}.mpeg", 'wb') as outfile:
                    outfile.write(data)


def calc_resolution(line):
    print(line)
    (x, y) = re.search("RESOLUTION=(\d+)x(\d+)", line).groups()
    return int(x) * int(y)


def audio(line):
    return re.search('AUDIO="([^"]+)"', line).group(1)


def group_id(line):
    return re.search('GROUP-ID="([^"]+)"', line).group(1)


def uri(line):
    return re.search('URI="([^"]+)"', line).group(1)


def form_encrypted_filename(encrypted_dir, index):
    return encrypted_dir / f"enc{index}.ts"


def form_segment_filename(segments_dir, index):
    return segments_dir / f"seg{index}.ts"


def is_absolute_uri(uri):
    return bool(urllib.parse.urlparse(uri).netloc)


def absolutize_uri(uri, root):
    if is_absolute_uri(uri):
        return uri
    else:
        p = urllib.parse.urlparse(root)
        return f"{p.scheme}://{p.netloc}{p.path.rsplit('/', 1)[0]}/{uri}"


def unsafe_urlopen(url, root=None):
    print(f"OPENING: {url} WITH ROOT {root}")
    if root:
        url = absolutize_uri(url, root)
        print(f"NEW URL: {url}")

    # user_agent = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7'
    gcontext = ssl.SSLContext()
    # headers = {"User-Agent": user_agent}
    headers = {}
    try:
        request = urllib.request.Request(url=url, headers=headers)
        return urllib.request.urlopen(request, context=gcontext)
    except ValueError:
        request = urllib.request.Request(url=root + '/' + url, headers=headers)
        return urllib.request.urlopen(request, context=gcontext)


def download_segment(index, segment_url, filename, root=None):
    print(f"[ ] Getting encrypted segment {index}...")
    segment_bytes = unsafe_urlopen(segment_url, root=root).read()  # NOTE: keep as bytes!
    with open(filename, 'wb') as outfile:
        outfile.write(segment_bytes)
    print(f"[+] {index} done.")


def download_segments(segment_urls, encrypted_dir, master_url_root):
    print("[ ] Downloading encrypted segments in parallel...")
    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_PROCESSES) as executor:
        for (index, segment_url) in enumerate(segment_urls):
            executor.submit(download_segment, index, segment_url, form_encrypted_filename(encrypted_dir, index), master_url_root)
    print("[+] Done.")


def decrypt_segments(segments, encrypted_dir, segments_dir, key):
    # TODO: make this skippable
    print("[ ] Decrypting segments...")
    for index in range(segments):
        encrypted_filename = form_encrypted_filename(encrypted_dir, index)
        segment_filename = form_segment_filename(segments_dir, index)
        with open(encrypted_filename, 'rb') as infile:
            with open(segment_filename, 'wb') as outfile:
                print(f"    [ ] Decrypting segment {index}...")
                encrypted_bytes = infile.read()
                if key:
                    decrypted_bytes = _decrypt(key, b"\x00" * 15 + bytes([index + 1]), encrypted_bytes)
                else:
                    decrypted_bytes = encrypted_bytes
                outfile.write(decrypted_bytes)
    print("[+] Done.")


def download_aes_key(master_url_root, index_text, meta_dir):
    # get AES keyfile
    key = None
    try:
        aes_line = [l for l in index_text.splitlines() if l.startswith("#EXT-X-KEY:")][0]
        aes_url = uri(aes_line)
        key = unsafe_urlopen(aes_url, root=master_url_root).read()  # NOTE: keep as bytes!
        with open(meta_dir / "encryption.key", 'wb') as outfile:
            outfile.write(key)
    except IndexError:
        pass  # no key

    return key


def concatenate_segments(path, segments, segments_dir):
    with open(path, "wb") as outfile:
        print("    [ ] Concatenating segments...")
        for index in range(segments):
            segment_filename = form_segment_filename(segments_dir, index)
            with open(segment_filename, 'rb') as infile:
                outfile.write(infile.read())
        print("    [+] Done.")


def download_m3u8(master_url, name_dir):
    master_url_root = master_url.rsplit("/", 1)[0]

    meta_dir = name_dir / "meta"
    if not meta_dir.exists():
        os.makedirs(meta_dir, exist_ok=True)

    video_dir = name_dir / "video"
    if not video_dir.exists():
        os.makedirs(video_dir, exist_ok=True)

    audio_dir = name_dir / "audio"
    if not audio_dir.exists():
        os.makedirs(audio_dir, exist_ok=True)

    encrypted_video_dir = name_dir / "video" / "encrypted"
    if not encrypted_video_dir.exists():
        os.makedirs(encrypted_video_dir, exist_ok=True)

    encrypted_audio_dir = name_dir / "audio" / "encrypted"
    if not encrypted_audio_dir.exists():
        os.makedirs(encrypted_audio_dir, exist_ok=True)

    video_segments_dir = name_dir / "video" / "segments"
    if not video_segments_dir.exists():
        os.makedirs(video_segments_dir, exist_ok=True)

    audio_segments_dir = name_dir / "audio" / "segments"
    if not audio_segments_dir.exists():
        os.makedirs(audio_segments_dir, exist_ok=True)

    # get master file
    master_text = unsafe_urlopen(master_url).read().decode('utf-8')
    with open(meta_dir / "master.m3u", 'w') as outfile:
        outfile.write(master_text)

    ### VIDEO
    # get video index url
    master_lines = master_text.split("\n#EXT-X-STREAM-INF:")[1:]
    target_line = max(master_lines, key=lambda l: calc_resolution(l))
    print(f"Target video line: {target_line}")
    video_index_url = absolutize_uri(target_line.split('\n')[1], master_url_root)

    # get video index file
    video_index_text = unsafe_urlopen(video_index_url, root=master_url_root).read().decode('utf-8')
    with open(meta_dir / "video-index-v1-a1.m3u", 'w') as outfile:
        outfile.write(video_index_text)

    # get video segment urls
    video_segment_lines = video_index_text.split("\n#EXTINF:")
    video_segment_urls = [l.split('\n')[1] for l in video_segment_lines][1:]
    video_segments = len(video_segment_urls)

    ### AUDIO
    has_separate_audio = ("AUDIO=" in target_line)
    audio_groups = {}
    audio_index_url = None
    if has_separate_audio:
        # get audio index url
        audio_groups = {group_id(l): uri(l) for l in master_text.split("\n") if l.startswith("#EXT-X-MEDIA:") and "TYPE=AUDIO" in l}
        audio_index_url = absolutize_uri(audio_groups[audio(target_line)], master_url_root)

        # get audio index file
        audio_index_text = unsafe_urlopen(audio_index_url, root=master_url_root).read().decode('utf-8')
        with open(meta_dir / "audio-index-v1-a1.m3u", 'w') as outfile:
            outfile.write(audio_index_text)

        # get audio segment urls
        audio_segment_lines = audio_index_text.split("\n#EXTINF:")
        audio_segment_urls = [l.split('\n')[1] for l in audio_segment_lines][1:]
        audio_segments = len(audio_segment_urls)

    # download AES key (may be null)
    key = download_aes_key(video_index_url, video_index_text, meta_dir)

    download_segments(video_segment_urls, encrypted_video_dir, video_index_url)

    if has_separate_audio:
        download_segments(audio_segment_urls, encrypted_audio_dir, audio_index_url)

    decrypt_segments(video_segments, encrypted_video_dir, video_segments_dir, key)

    if has_separate_audio:
        decrypt_segments(audio_segments, encrypted_audio_dir, audio_segments_dir, key)

    print("[ ] Processing final video file...")
    video_file_name = video_dir / "video.ts"
    concatenate_segments(video_file_name, video_segments, video_segments_dir)

    print("[ ] Processing final audio file...")
    audio_file_name = None
    if has_separate_audio:
        audio_file_name = audio_dir / "audio.ts"
        concatenate_segments(audio_file_name, audio_segments, audio_segments_dir)

    print("[ ] Converting file with ffmpeg...")
    outfile_name = str(name_dir / name_dir.name) + ".mp4"
    subprocess.check_output(["ffmpeg", "-i", video_file_name] + (["-i", audio_file_name] if has_separate_audio else []) + ["-acodec", "copy", "-vcodec", "copy", outfile_name])
    print("[+] Complete.")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("master_url")
    parser.add_argument("-s", "--skip", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    master_url = args.master_url
    name = args.name

    if not SAVES.exists():
        os.mkdir(SAVES)

    name_dir = SAVES / name
    if name_dir.exists():  # NOTE: case-insensitive on Mac
        if args.skip:
            print(f"[*] Skipping pre-existing directory {repr(name)}")
            return
        if input("[?] That name already exists.  Continue anyway? ") not in set('yY'):
            return
    else:
        os.mkdir(name_dir)

    download_m3u8(master_url, name_dir)


if __name__ == '__main__':
    main()
