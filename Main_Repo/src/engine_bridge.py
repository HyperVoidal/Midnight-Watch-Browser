import ctypes
import os
import sys
from adblock import Engine, FilterSet
from pathlib import Path
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInfo
srcSourceDir = Path(__file__).parent

def get_library():
    #Locate .so file for processing in the build path
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lib_path = os.path.join(base_path, "build", "libMidnightCPP.so")
    
    if not os.path.exists(lib_path):
        raise FileNotFoundError(f"C++ Library not found at {lib_path}. Did you run 'make'?")

    #Load the library
    midnight_lib = ctypes.CDLL(lib_path)

    #Define the argument and return types for verify_url_safe
    #This is crucial so Python doesn't crash the C++ side
    midnight_lib.verify_url_safe.argtypes = [ctypes.c_char_p]
    midnight_lib.verify_url_safe.restype = ctypes.c_int
    
    return midnight_lib

#Initialise the library
try:
    midnight_core = get_library()
except Exception as e:
    print(f"Error loading C++ core: {e}")
    midnight_core = None


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

# engine_bridge.py

# engine_bridge.py

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
    # Map the resource type using the RESOURCE_MAP from earlier
    rtype = RESOURCE_MAP.get(qt_resource_type, "other")
    
    # check_network_urls returns a BlockerResult object
    result = engine.check_network_urls(url, source_url, rtype)
    
    # BlockerResult has a .matched attribute (True if it should be blocked)
    return not result.matched
