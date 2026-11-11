"""산재TV(노무법인산재) 유튜브 새 영상을 news.json에 자동으로 추가합니다.

- 유튜브 채널 RSS(최근 영상 약 15개)를 읽어, news.json에 없는 영상만 추가합니다.
- rejected.json에 있는 주소(내려 달라고 한 소식)는 다시 추가하지 않습니다.
- 기존 항목은 절대 지우거나 바꾸지 않습니다.
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

CHANNEL_ID = "UCEAErnUNunr3EjphGoA4eEg"
FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
ROOT = Path(__file__).resolve().parent.parent
NEWS = ROOT / "news.json"
REJECTED = ROOT / "rejected.json"
KST = timezone(timedelta(hours=9))
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


def video_id_of(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", url or "")
    return m.group(1) if m else None


def fetch_feed():
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 (peoplegroup-news feed reader)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    for e in root.findall("a:entry", NS):
        vid = e.findtext("yt:videoId", namespaces=NS)
        title = (e.findtext("a:title", namespaces=NS) or "").strip()
        published = e.findtext("a:published", namespaces=NS) or ""
        if not vid or not title:
            continue
        date = ""
        try:
            date = datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(KST).strftime("%Y-%m-%d")
        except ValueError:
            pass
        out.append({"vid": vid, "title": title, "date": date})
    return out


def main(feed_file=None):
    xml_bytes = Path(feed_file).read_bytes() if feed_file else fetch_feed()
    videos = parse(xml_bytes)
    if not videos:
        print("영상 목록이 비어 있음 - 변경 없음")
        return

    raw = NEWS.read_text(encoding="utf-8")
    data = json.loads(raw)
    items = data["items"]

    known = {video_id_of(i.get("url")) for i in items} - {None}
    known |= {i.get("id", "")[3:] for i in items if i.get("id", "").startswith("yt-")}
    if REJECTED.exists():
        for r in json.loads(REJECTED.read_text(encoding="utf-8")):
            v = video_id_of(r if isinstance(r, str) else r.get("url"))
            if v:
                known.add(v)

    added = []
    for v in videos:
        if v["vid"] in known:
            continue
        added.append({
            "id": f"yt-{v['vid']}",
            "date": v["date"],
            "org": "sanjae",
            "type": "소식",
            "title": f"[산재TV] {v['title']}",
            "summary": "",
            "url": f"https://www.youtube.com/watch?v={v['vid']}",
            "source": "산재TV 노무법인산재 (유튜브)",
        })
        known.add(v["vid"])

    if not added:
        print("새 영상 없음")
        return

    items.extend(added)
    # 날짜 최신순(날짜 없는 항목은 맨 뒤), 같은 날짜는 기존 순서 유지
    dated = sorted([i for i in items if i.get("date")], key=lambda i: i["date"], reverse=True)
    undated = [i for i in items if not i.get("date")]
    data["items"] = dated + undated
    data["updated"] = datetime.now(KST).strftime("%Y-%m-%d")
    NEWS.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for a in added:
        print("추가:", a["date"], a["title"], a["url"])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
