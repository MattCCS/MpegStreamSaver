
import json
import urllib.request

URL = "http://www.adultswim.com/videos/cowboy-bebop"
resp = urllib.request.urlopen(URL)
body = resp.read().decode("utf-8")

print(json.dumps(json.loads(body.split("__NEXT_DATA__")[1].split("__NEXT_LOADED_PAGES__")[0].lstrip(" =").rstrip(";")), indent=4))
