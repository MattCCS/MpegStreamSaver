import base64
import getpass
from urllib import request

# vid = "1ec939ba9c664501b4d0d2e009c45d79"  # wrong
# vid = "1a959fc85caf1a960d36bddd15c67e7178fcae13"  # wrong
vid = "26ea0b7c93403485584ee0540a22480d"  # good, manual

appIdE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6ImFzLXR2ZS1kZXNrdG9wLXB0enQ2bSIsInByb2R1Y3QiOiJ0dmUiLCJuZXR3b3JrIjoiYXMiLCJwbGF0Zm9ybSI6ImRlc2t0b3AiLCJpYXQiOjE1MzI3MDIyNzl9."

# print(base64.b64decode(appIdE))

FORM = "https://token.ngtv.io/token/token_spe?format=json&appId={}&path=%2Fadultswim%2F{}%2Fmaster_bk_de.m3u8&&"
url = FORM.format(appIdE, vid)
# print(request.urlopen(url).read().decode('utf-8'))


# print(base64.b64decode(b"VklERU86RDBYOXdZUFJTYkc2Z2s0VHlaRGdTZw=="))
# print(base64.b64encode(b"3096a32386c005ac986c1e3a0a22d08e"))

# print(base64.b64encode(b"26ea0b7c93403485584ee0540a22480d"))
# print(base64.b16decode(b"26ea0b7c93403485584ee0540a22480d"))


########################################


MASTER_FORM = "https://tve.cdn.turner.com/adultswim/{}/master_bk_de.m3u8?hdnts={}"


def f():
    inp = getpass.getpass("")
    inp = "exp=" + inp.split("exp=", 1)[1].rstrip(', "')
    vid = inp.split("/")[2]
    return MASTER_FORM.format(vid, inp)


print(f())
