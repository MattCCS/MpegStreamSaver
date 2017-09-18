"""
A tool to grab Mpeg Streams

See for details:
    https://tools.ietf.org/html/draft-pantos-http-live-streaming-07
"""

import os
import pathlib
import subprocess
import tempfile
import concurrent.futures
import urllib.request

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


ROOT = pathlib.Path(__file__).absolute().parent
SAVES = ROOT / "saves"


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
                encrypted_data = urllib.request.urlopen(line).read()

                i += 1
                print(f"Writing {i}")
                data = _decrypt(key, b"\x00" * 15 + bytes([i]), encrypted_data)

                with open(f"part{i}.mpeg", 'wb') as outfile:
                    outfile.write(data)


def form_encrypted_filename(encrypted_dir, index):
    return encrypted_dir / f"enc{index}.ts"


def form_segment_filename(segments_dir, index):
    return segments_dir / f"seg{index}.ts"


def download_segment(index, segment_url, filename):
    print(f"[ ] Getting encrypted segment {index}...")
    segment_bytes = urllib.request.urlopen(segment_url).read()  # NOTE: keep as bytes!
    with open(filename, 'wb') as outfile:
        outfile.write(segment_bytes)
    print(f"[+] {index} done.")


def download_segments(master_url, name_dir):
    meta_dir = name_dir / "meta"
    if not meta_dir.exists():
        os.mkdir(meta_dir)

    encrypted_dir = name_dir / "encrypted"
    if not encrypted_dir.exists():
        os.mkdir(encrypted_dir)

    segments_dir = name_dir / "segments"
    if not segments_dir.exists():
        os.mkdir(segments_dir)

    # get master file
    master_text = urllib.request.urlopen(master_url).read().decode('utf-8')
    with open(meta_dir / "master.m3u", 'w') as outfile:
        outfile.write(master_text)

    # get index url
    master_lines = master_text.split("\n#EXT-X-STREAM-INF:")
    target_line = [l for l in master_lines if "RESOLUTION=1920x1080" in l and "akamai" in l][0]
    index_url = target_line.split('\n')[1]

    # get index file
    index_text = urllib.request.urlopen(index_url).read().decode('utf-8')
    with open(meta_dir / "index-v1-a1.m3u", 'w') as outfile:
        outfile.write(index_text)

    # get AES keyfile
    aes_line = [l for l in index_text.splitlines() if l.startswith("#EXT-X-KEY:")][0]
    aes_url = aes_line.split('''#EXT-X-KEY:METHOD=AES-128,URI="''')[1].rstrip('"')
    key = urllib.request.urlopen(aes_url).read()  # NOTE: keep as bytes!
    with open(meta_dir / "encryption.key", 'wb') as outfile:
        outfile.write(key)

    # get segment urls
    segment_lines = index_text.split("\n#EXTINF:")
    segment_urls = [l.split('\n')[1] for l in segment_lines][1:]
    segments = len(segment_urls)

    print("[ ] Downloading encrypted segments in parallel...")
    with concurrent.futures.ProcessPoolExecutor(max_workers=5) as executor:
        for (index, segment_url) in enumerate(segment_urls):
            executor.submit(download_segment, index, segment_url, form_encrypted_filename(encrypted_dir, index))
    print("[+] Done.")

    print("[ ] Decrypting segments...")
    for index in range(segments):
        encrypted_filename = form_encrypted_filename(encrypted_dir, index)
        segment_filename = form_segment_filename(segments_dir, index)
        with open(encrypted_filename, 'rb') as infile:
            with open(segment_filename, 'wb') as outfile:
                print(f"    [ ] Decrypting segment {index}...")
                encrypted_bytes = infile.read()
                decrypted_bytes = _decrypt(key, b"\x00" * 15 + bytes([index + 1]), encrypted_bytes)
                outfile.write(decrypted_bytes)
    print("[+] Done.")

    print("[ ] Processing final video file...")
    with tempfile.NamedTemporaryFile() as tfile:
        print("    [ ] Concatenating segments...")
        for index in range(segments):
            segment_filename = form_segment_filename(segments_dir, index)
            with open(segment_filename, 'rb') as infile:
                tfile.write(infile.read())
        tfile.flush()
        print("    [+] Done.")

        print("    [ ] Converting file with ffmpeg...")
        infile_name = tfile.name
        outfile_name = str(name_dir / name_dir.name) + ".mp4"
        subprocess.check_output(["ffmpeg", "-i", infile_name, "-acodec", "copy", "-vcodec", "copy", outfile_name])
        print("    [+] Done.")
    print("[+] Complete.")


def main():
    if not SAVES.exists():
        os.mkdir(SAVES)

    name = input("Directory name: ")
    name_dir = SAVES / name
    if name_dir.exists():  # NOTE: case-insensitive on Mac
        if input("[?] That name already exists.  Continue anyway? ") not in set('yY'):
            return
    else:
        os.mkdir(name_dir)

    master_url = input("Paste URL to master manifest (.m3u file) here: ")
    assert master_url

    download_segments(master_url, name_dir)


if __name__ == '__main__':
    main()
