import ctypes
import os
import sys
from adblock import Engine, FilterSet
from pathlib import Path
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInfo
from PySide6.QtCore import QTimer
import platform
from path_utils import resolve_source_dir

OPERATING_SYSTEM = platform.system()

srcSourceDir = resolve_source_dir(__file__)
    

def load_engine():
    try:
        path = srcSourceDir / "data" / "urlblockerlist.txt"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                #create filterset
                filter_set = FilterSet()
                #splitlines list conversion
                filter_set.add_filters(f.read().splitlines())
                #pass filterset to engine
                return Engine(filter_set)
    except Exception as e:
        print(f"Failed to load engine: {e}")
    
    # Fallback to an empty FilterSet if file is missing
    return Engine(FilterSet())

# Initialise engine from filter lists
engine = load_engine()

# Map Qt Enums to strings that adblock-python understands
RESOURCE_MAP = {
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMainFrame: "document",
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypeSubFrame: "subdocument",
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypeStylesheet: "stylesheet",
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypeScript: "script",
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypeImage: "image",
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypeXhr: "xmlhttprequest",
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypePrefetch: "xmlhttprequest",
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypePing: "ping",
    QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMedia: "media",
}

YOUTUBE_ALLOWLIST = [
    "static.doubleclick.net/instream/ad_status.js",
    "i.ytimg.com/generate_204",
    "googlevideo.com/generate_204",
]

def get_cosmetic_filters(url: str):
    try:
        # Get the resources object for the specific URL
        resources = engine.url_cosmetic_resources(url)
        
        # Try retrieving the stylesheet (some versions use .style_sheet, some .stylesheet)
        css_code = getattr(resources, 'style_sheet', getattr(resources, 'stylesheet', ""))
        
        # If no full stylesheet is provided, check for hide_selectors (list of tags)
        if not css_code and hasattr(resources, 'hide_selectors'):
            selectors = resources.hide_selectors
            if selectors:
                css_code = ", ".join(selectors) + " { display: none !important; }"

        return css_code if css_code else ""
    except Exception as e:
        print(f"Midnight Shield: Cosmetic Error - {e}")
        return ""

def get_scriptlets(url: str):
    try:
        resources = engine.url_cosmetic_resources(url)
        
        # Check both potential attribute names
        script_code = getattr(resources, 'scriptlets', getattr(resources, 'injected_script', ""))
        
        return script_code if script_code else ""
    except Exception as e:
        print(f"Midnight Shield: Scriptlet Retrieval Error - {e}")
        return ""


def is_url_safe(url: str, source_url: str, qt_resource_type):

    # Allow critical YouTube playback/probe URLs
    if "youtube.com" in source_url:

        for allowed in YOUTUBE_ALLOWLIST:
            if allowed in url:
                return True

    rtype = RESOURCE_MAP.get(qt_resource_type, "other")

    result = engine.check_network_urls(
        url,
        source_url,
        rtype
    )

    return not result.matched