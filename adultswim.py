
import argparse
import base64
import json
import re
import sys
from collections import OrderedDict
import urllib.request


ADULT_SWIM_SERIES_PAGE_MEDIA_ID_REGEX = r'''"_id":"([^\"]+)"'''

ADULT_SWIM_MEDIA_URL_FORMAT = "http://www.adultswim.com/api/shows/v1/media/{media_id}/desktop"

ADULT_SWIM_APP_ID = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6ImFzLXR2ZS1kZXNrdG9wLXB0enQ2bSIsInByb2R1Y3QiOiJ0dmUiLCJuZXR3b3JrIjoiYXMiLCJwbGF0Zm9ybSI6ImRlc2t0b3AiLCJpYXQiOjE1MzI3MDIyNzl9."

ADULT_SWIM_TOKEN_URL_FORMAT = "https://token.ngtv.io/token/token_spe?format=json&appId={app_id}&path=%2Fadultswim%2F{asset_id}%2Fmaster_bk_de.m3u8&&"

ADULT_SWIM_MASTER_URL_FORMAT = "https://tve.cdn.turner.com/adultswim/{asset_id}/master_bk_de.m3u8?hdnts={token_params}"


def err(text):
    sys.stderr.write(str(text) + "\n")
    sys.stderr.flush()


def out(text):
    sys.stdout.write(text)
    sys.stdout.flush()


def format_media_url(media_id):
    return ADULT_SWIM_MEDIA_URL_FORMAT.format(media_id=media_id)


def form_token_url(asset_id):
    return ADULT_SWIM_TOKEN_URL_FORMAT.format(app_id=ADULT_SWIM_APP_ID, asset_id=asset_id)


def form_master_url(asset_id, token_params):
    return ADULT_SWIM_MASTER_URL_FORMAT.format(asset_id=asset_id, token_params=token_params)


def read_html(url):
    return urllib.request.urlopen(url).read().decode("utf-8")


def find_series_json(text):
    return json.loads(
        text.split("__NEXT_DATA__")[1].split("__NEXT_LOADED_PAGES__")[0].lstrip(" =").rstrip(";"),
        object_pairs_hook=OrderedDict)


def find_all_media_ids(text):
    return re.findall(ADULT_SWIM_SERIES_PAGE_MEDIA_ID_REGEX, text)


def find_all_media(text):
    series_json = find_series_json(text)
    series_slug = series_json["props"]["__REDUX_STATE__"]["router"]["query"]["show"]
    series_title = None

    season = None
    # get initial season, because loading a specific episode page changes its relative position
    for (key, value) in series_json["props"]["__APOLLO_STATE__"].items():
        if key.startswith("Season:"):
            season = value["name"].split("Season ")[1]
            break

    episodes = []
    for (key, value) in series_json["props"]["__APOLLO_STATE__"].items():
        if key.startswith("Season:"):
            season = value["name"].split("Season ")[1]

        elif key.startswith("VideoCollection:"):
            series_title = value["title"]

        elif key.startswith("Video:"):
            episode_number = str(value["episodeNumber"])
            episode_title = value["title"]
            media_id = value["_id"]
            episode_slug = value["slug"]

            episodes.append({
                "season": season,
                "episode_number": episode_number,
                "episode_title": episode_title,
                "episode_slug": episode_slug,
                "media_id": media_id,
            })

    return {
        "series_title": series_title,
        "series_slug": series_slug,
        "episodes": {
            e["episode_slug"]: e
            for e in episodes
        },
    }


def get_master_url(episode):
    media_id = episode["media_id"]
    err(media_id)
    asset_id = get_asset_id(media_id)
    err(asset_id)
    token_url = form_token_url(asset_id)
    err(token_url)
    token_params = get_token_params(read_html(token_url))
    err(token_params)
    master_url = form_master_url(asset_id, token_params)
    err(master_url)

    return master_url


def get_warez_name(media, episode):
    series = media["series_title"].replace(" ", "").strip()
    season = "{:>02}".format(episode["season"])
    episode_number = "{:>02}".format(episode["episode_number"])
    episode_title = episode["episode_title"].replace(" ", "").strip()
    return f"{series}_S{season}_E{episode_number}_{episode_title}"


def get_warez_info(media, episode_slug):
    episode = media["episodes"][episode_slug]
    err(json.dumps(episode, indent=4))
    return {
        "name": get_warez_name(media, episode),
        "url": get_master_url(episode),
    }


def get_asset_id(media_id):
    media_url = format_media_url(media_id)
    asset_html = read_html(media_url)
    return json.loads(asset_html)["media"]["desktop"]["multidrm"]["assetId"]


def get_token_params(text):
    return json.loads(text)["auth"]["token"]


def get_episode_slug(url):
    return url.rstrip("/").rsplit("/", 1)[1]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("root_url")
    return parser.parse_args()


def main():
    args = parse_args()
    err(args.root_url)

    media = find_all_media(read_html(args.root_url))
    episode_slug = get_episode_slug(args.root_url)

    if episode_slug not in media["episodes"]:
        err(json.dumps(media, indent=4))
        err(f"[-] No episode slug found in URL (got {repr(episode_slug)}).")
        out("\n".join(media["episodes"]) + "\n")
        return

    warez_info = get_warez_info(media, episode_slug)
    err(json.dumps(warez_info, indent=4))

    out(f'{warez_info["name"]} {warez_info["url"]}')


if __name__ == '__main__':
    main()
