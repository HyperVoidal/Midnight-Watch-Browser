from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from engine_bridge import is_url_safe

class AdInterceptor(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        #Get url of subrequest
        url = info.requestUrl().toString()
        
        #Check with gatekeeper
        if not is_url_safe(url):
            print(f"Midnight Shield: BLOCKED {url}")
            info.block(True)
