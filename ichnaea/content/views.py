"""
Contains website related routes and views.
"""

from operator import itemgetter
import os
from urllib import parse as urlparse

import boto3
from boto3.exceptions import Boto3Error
from botocore.exceptions import BotoCoreError
from pyramid.decorator import reify
from pyramid.events import NewResponse
from pyramid.events import subscriber
from pyramid.renderers import get_renderer
from pyramid.response import FileResponse
from pyramid.response import Response
from pyramid.view import view_config
import simplejson

from ichnaea.conf import settings
from ichnaea.content.stats import global_stats, histogram, regions
from ichnaea.models.content import StatKey
from ichnaea import util

HERE = os.path.dirname(__file__)
IMAGE_PATH = os.path.join(HERE, "static", "images")
FAVICON_PATH = os.path.join(IMAGE_PATH, "favicon.ico")
TOUCHICON_PATH = os.path.join(IMAGE_PATH, "apple-touch-icon.png")

CSP_BASE = "'self'"
CSP_POLICY = """\
default-src 'self' *.tiles.mapbox.com;
font-src {base};
img-src {base} {tiles} *.google-analytics.com *.tiles.mapbox.com data:;
script-src {base} *.google-analytics.com data: 'unsafe-eval';
style-src {base};
"""
CSP_POLICY = CSP_POLICY.replace("\n", " ").strip()
TILES_PATTERN = "{z}/{x}/{y}.png"
HOMEPAGE_MAP_IMAGE = (
    "https://a.tiles.mapbox.com/v4/mapbox.dark" "/0/0/0@2x.png?access_token={token}"
)


def configure_tiles_url(asset_url):
    asset_url = asset_url if asset_url else ""
    if not asset_url.endswith("/"):
        asset_url = asset_url + "/"
    tiles_url = urlparse.urljoin(asset_url, "tiles/" + TILES_PATTERN)

    result = urlparse.urlsplit(tiles_url)
    tiles_src = urlparse.urlunparse((result.scheme, result.netloc, "", "", "", ""))
    return (tiles_src, tiles_url)


MAP_TILES_SRC, MAP_TILES_URL = configure_tiles_url(settings("asset_url"))
CSP_POLICY = CSP_POLICY.format(base=CSP_BASE, tiles=MAP_TILES_SRC)


def configure_content(config):
    config.add_view(
        favicon_view, name="favicon.ico", http_cache=(86400, {"public": True})
    )
    config.registry.skip_logging.add("/favicon.ico")
    config.add_view(
        robotstxt_view, name="robots.txt", http_cache=(86400, {"public": True})
    )
    config.registry.skip_logging.add("/robots.txt")
    config.add_view(
        touchicon_view,
        name="apple-touch-icon-precomposed.png",
        http_cache=(86400, {"public": True}),
    )
    config.registry.skip_logging.add("/apple-touch-icon-precomposed.png")
    config.add_static_view(
        name="static", path="ichnaea.content:static", cache_max_age=86400
    )

    config.add_route("stats_regions", "/stats/regions")
    config.add_route("stats", "/stats")

    config.scan("ichnaea.content.views")


@subscriber(NewResponse)
def security_headers(event):
    response = event.response
    # Headers for all responses.
    response.headers.add(
        "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
    )
    response.headers.add("X-Content-Type-Options", "nosniff")
    # Headers for HTML responses.
    if response.content_type == "text/html":
        response.headers.add("Content-Security-Policy", CSP_POLICY)
        response.headers.add("X-Frame-Options", "DENY")
        response.headers.add("X-XSS-Protection", "1; mode=block")


def s3_list_downloads(raven_client):
    files = {"full": [], "diff1": [], "diff2": []}

    if not settings("asset_bucket"):
        return files

    asset_url = settings("asset_url")
    if not asset_url.endswith("/"):
        asset_url = asset_url + "/"

    diff = []
    full = []
    try:
        s3 = boto3.resource("s3")
        bucket = s3.Bucket(settings("asset_bucket"))
        for obj in bucket.objects.filter(Prefix="export/"):
            name = obj.key.split("/")[-1]
            path = urlparse.urljoin(asset_url, obj.key)
            # round to kilobyte
            size = int(round(obj.size / 1024.0, 0))
            file = dict(name=name, path=path, size=size)
            if "diff-" in name:
                diff.append(file)
            elif "full-" in name:
                full.append(file)
    except (Boto3Error, BotoCoreError):
        raven_client.captureException()
        return files

    half = len(diff) // 2 + len(diff) % 2
    diff = list(sorted(diff, key=itemgetter("name"), reverse=True))
    files["diff1"] = diff[:half]
    files["diff2"] = diff[half:]
    files["full"] = list(sorted(full, key=itemgetter("name"), reverse=True))
    return files


class ContentViews(object):
    def __init__(self, request):
        self.request = request
        self.session = request.db_session
        self.redis_client = request.registry.redis_client

    @reify
    def base_template(self):
        renderer = get_renderer("templates/base.pt")
        return renderer.implementation().macros["layout"]

    @property
    def this_year(self):
        return "%s" % util.utcnow().year

    def _get_cache(self, cache_key):
        cache_key = self.redis_client.cache_keys[cache_key]
        cached = self.redis_client.get(cache_key)
        if cached:
            return simplejson.loads(cached)
        return None

    def _set_cache(self, cache_key, data, ex=3600):
        cache_key = self.redis_client.cache_keys[cache_key]
        self.redis_client.set(cache_key, simplejson.dumps(data), ex=ex)

    def is_map_enabled(self):
        """Return whether maps are enabled.

        Enable maps if and only if there's a mapbox token and a url for the
        tiles location. Otherwise it's disabled.

        """
        return bool(MAP_TILES_URL and settings("mapbox_token"))

    @view_config(renderer="templates/homepage.pt", http_cache=3600)
    def homepage_view(self):
        image_base_url = HOMEPAGE_MAP_IMAGE.format(token=settings("mapbox_token"))
        image_url = MAP_TILES_URL.format(z=0, x=0, y="0@2x")
        return {
            "page_title": "Overview",
            "map_enabled": self.is_map_enabled(),
            "map_image_base_url": image_base_url,
            "map_image_url": image_url,
        }

    @view_config(renderer="templates/api.pt", name="api", http_cache=3600)
    def api_view(self):
        return {"page_title": "API"}

    @view_config(renderer="templates/contact.pt", name="contact", http_cache=3600)
    def contact_view(self):
        return {"page_title": "Contact Us"}

    @view_config(renderer="templates/downloads.pt", name="downloads", http_cache=3600)
    def downloads_view(self):
        data = self._get_cache("downloads")
        if data is None:
            data = s3_list_downloads(self.request.registry.raven_client)
            self._set_cache("downloads", data, ex=1800)
        return {"page_title": "Downloads", "files": data}

    @view_config(renderer="templates/optout.pt", name="optout", http_cache=3600)
    def optout_view(self):
        return {"page_title": "Opt-Out"}

    @view_config(renderer="templates/privacy.pt", name="privacy", http_cache=3600)
    def privacy_view(self):
        return {"page_title": "Privacy Notice"}

    @view_config(renderer="templates/map.pt", name="map", http_cache=3600)
    def map_view(self):
        return {
            "page_title": "Map",
            "map_enabled": self.is_map_enabled(),
            "map_tiles_url": MAP_TILES_URL,
            "map_token": settings("mapbox_token"),
        }

    @view_config(renderer="json", name="map.json", http_cache=3600)
    def map_json(self):
        offset = MAP_TILES_URL.find(TILES_PATTERN)
        base_url = MAP_TILES_URL[:offset]
        return {"tiles_url": base_url}

    @view_config(renderer="json", name="stats_blue.json", http_cache=3600)
    def stats_blue_json(self):
        data = self._get_cache("stats_blue_json")
        if data is None:
            data = histogram(self.session, StatKey.unique_blue)
            self._set_cache("stats_blue_json", data)
        return {"series": [{"title": "MLS Bluetooth", "data": data[0]}]}

    @view_config(renderer="json", name="stats_cell.json", http_cache=3600)
    def stats_cell_json(self):
        data = self._get_cache("stats_cell_json")
        if data is None:
            data = histogram(self.session, StatKey.unique_cell)
            self._set_cache("stats_cell_json", data)
        return {"series": [{"title": "MLS Cells", "data": data[0]}]}

    @view_config(renderer="json", name="stats_wifi.json", http_cache=3600)
    def stats_wifi_json(self):
        data = self._get_cache("stats_wifi_json")
        if data is None:
            data = histogram(self.session, StatKey.unique_wifi)
            self._set_cache("stats_wifi_json", data)
        return {"series": [{"title": "MLS WiFi", "data": data[0]}]}

    @view_config(renderer="templates/stats.pt", route_name="stats", http_cache=3600)
    def stats_view(self):
        data = self._get_cache("stats")
        if data is None:
            data = {"metrics1": [], "metrics2": []}
            metric_names = [
                ("1", StatKey.unique_blue.name, "Bluetooth Networks"),
                ("1", StatKey.blue.name, "Bluetooth Observations"),
                ("1", StatKey.unique_wifi.name, "Wifi Networks"),
                ("1", StatKey.wifi.name, "Wifi Observations"),
                ("2", StatKey.unique_cell.name, "MLS Cells"),
                ("2", StatKey.cell.name, "MLS Cell Observations"),
            ]
            metrics = global_stats(self.session)
            for i, mid, name in metric_names:
                data["metrics" + i].append({"name": name, "value": metrics[mid]})
            self._set_cache("stats", data)

        result = {"page_title": "Statistics"}
        result.update(data)
        return result

    @view_config(
        renderer="templates/stats_regions.pt",
        route_name="stats_regions",
        http_cache=3600,
    )
    def stats_regions_view(self):
        data = self._get_cache("stats_regions")
        if data is None:
            data = regions(self.session)
            self._set_cache("stats_regions", data)
        return {"page_title": "Regions", "metrics": data}

    @view_config(renderer="templates/terms.pt", name="terms", http_cache=3600)
    def terms_of_service(self):
        return {
            "page_title": (
                "Developer Terms of Service:" " Mozilla Location Service Query API"
            )
        }


def favicon_view(request):
    return FileResponse(FAVICON_PATH, request=request)


def touchicon_view(request):
    return FileResponse(TOUCHICON_PATH, request=request)


_ROBOTS_RESPONSE = """\
User-agent: *
Disallow: /downloads
Disallow: /static/
Disallow: /v1/
Disallow: /v2/
Disallow: /__heartbeat__
Disallow: /__lbheartbeat__
Disallow: /__version__
"""


def robotstxt_view(context, request):
    return Response(content_type="text/plain", body=_ROBOTS_RESPONSE)
