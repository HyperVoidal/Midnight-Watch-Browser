import PySide6
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtWebEngineWidgets import *
from PySide6.QtWebEngineCore import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtNetwork import *
from PySide6.QtWebEngineCore import *
from PySide6.QtWebChannel import *
from pathlib import Path
import os
import json
from engine_bridge import is_url_safe, get_cosmetic_filters, get_scriptlets
from ui_core import additionalUIElements



srcSourceDir = Path(__file__).parent

BASE_DIR = (Path(srcSourceDir)/"ui").resolve()


class InternalPage(QWebEnginePage):

    def __init__(self, profile, browser, parent=None):
        super().__init__(profile, parent)
        self.additionalUIElements = additionalUIElements(self)
        self.browser = browser
        self.parent = parent

    def createWindow(self, webWindowType):
        try:
            req_url = self.requestedUrl()
        except Exception:
            req_url = None

        if self.additionalUIElements.WindowConfirmation("Redirect", f"Allow new window to open:\n{req_url.toString() if req_url else 'Unknown URL'}?"):

            if self.parent and hasattr(self.parent, "add_new_tab"):
                if req_url and not req_url.isEmpty():
                    new_view = self.parent.add_new_tab(qurl=req_url)
                else:
                    new_view = self.parent.add_new_tab()
                return new_view.page()

            # Fallback: standalone popup window
            new_view = QWebEngineView()
            new_page = InternalPage(self.profile() if callable(getattr(self, "profile", None)) else self.profile, new_view)
            new_view.setPage(new_page)
            new_view.setAttribute(Qt.WA_DeleteOnClose)
            new_view.resize(1200, 800)
            new_view.show()
            return new_page
        
    def acceptNavigationRequest(self, url, nav_type, is_mainframe):
        print("NAV REQUEST: " + str(url))

        if not is_mainframe:
            return True

        scheme = url.scheme().lower()

        # internal resources always OK
        if scheme == "midnightwatch":
            return True
        
        # User-initiated actions are always allowed
        allowed = {
            QWebEnginePage.NavigationType.NavigationTypeTyped,
            QWebEnginePage.NavigationType.NavigationTypeOther,
            QWebEnginePage.NavigationType.NavigationTypeLinkClicked,
            QWebEnginePage.NavigationType.NavigationTypeBackForward,
            QWebEnginePage.NavigationType.NavigationTypeReload,
            QWebEnginePage.NavigationType.NavigationTypeFormSubmitted
        }
        
        if nav_type in allowed:
            return True

        # Handle Redirects
        if nav_type == QWebEnginePage.NavigationType.NavigationTypeRedirect:
            if url.scheme() == "midnightwatch":
                return True
            
            # user intentionally left internal space
            if self.requestedUrl().scheme() in ("http", "https"):
                return True

            # allow same-origin redirects
            if url.host() == self.url().host():
                return True

            # prompt for cross-origin redirects
            return self.additionalUIElements.WindowConfirmation("Redirect", f"Allow redirect to:\n{url.toString()}?")

        print(f"Blocked internal navigation ({nav_type}) -> {url.toString()}")
        return False




class UrlCustomSchemeManager(QWebEngineUrlSchemeHandler):
    #MIME Whitelist
    MIME_MAP = {
        ".html":"text/html",
        ".css":"text/css",
        ".js":"application/javascript",
        ".png":"image/png",
        ".jpg":"image/jpeg",
        ".jpeg":"image/jpeg",
        ".svg":"image/svg+xml",
        ".json":"application/json",
        ".gif":"image/gif",
    }

    def requestStarted(self, job):
        url = job.requestUrl()
        relative = url.path().lstrip('/')
        target = (BASE_DIR/relative).resolve()

        #Traversal protection
        try:
            target.relative_to(BASE_DIR)
        except ValueError:
            print(f"Midnight Shield: traversal blocked -> {target}")
            job.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
            return
        
        #Check that it actually works
        if not target.exists():
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return
        
        #Avoid giving any job an agreement if the request comes from a non-local source file
        if url.host().lower() != "local":
            job.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
            return

        #Deny unknown extensoins
        mime = self.MIME_MAP.get(target.suffix.lower())
        if not mime:
            print(f"Midnight Shield: unsupported mime -> {target}")
            job.fail(QWebEngineUrlRequestJob.Error.UrlInvalid)
            return

        #Filesystem root sandbox
        file = QFile(str(target))
        file.setParent(job)

        if not file.open(QIODevice.OpenModeFlag.ReadOnly):
            job.fail(QWebEngineUrlRequestJob.Error.RequestFailed)
            return

        job.reply(mime.encode(), file)




class UrlManager():
    def __init__(self):
        pass

    def normalise_url_storage(navlink: bool, url_input: str):
        pass

    def normalise_url(navlink: bool, url_input: str):
        qurl = QUrl.fromUserInput(url_input)

        # Guard clause for invalid URLs
        if not qurl.isValid():
            return ""
        
        #Guard clause for html files like the homepage
        if qurl.scheme() == "file":
            return qurl.toString()

        # Force lowercase host
        qurl.setHost(qurl.host().lower())

        # Remove default ports
        if qurl.port() in (80, 443):
            qurl.setPort(-1)

        # Strip tracking query params
        query = QUrlQuery(qurl)
        clean_query = QUrlQuery()

        for key, value in query.queryItems():
            #Parameter list
            Tracking_Parameters = [
                "utm_",
                "si",
                "sei",
                "fbclid",
                "gclid",
                "sg_ss",
                "ved",
                "ei",
                "source",
                "gs_lcrp",
                "sca_esv",
                "iflsig",
                "uact",
                "oq",
                "aqs",
                "mc",
                "mc_eid",
                "mc_cid",
                "mkt_tok",
                "yclid",
                "dclid",
                "gbraid",
                "wbraid",
                "msclkid",
                "ttclid",
                "twclid",
                "igshid",
                "ref_src",
                "ref_url",
                "s_cid",
                "vero_id",
                "oly_anon_id",
                "oly_enc_id",
                "_pk_id",
                "_pk_ses",
                "rb_clickid",
                "wickedid",
                "cmpid",
                "campid",
                "__hsfp",
                "__hssc",
                "_s",
                "_hsenc",
                "_openstat",
                "hsCtaTracking",
                "ml_subscriber",
                "ml_subscriber_hash",
                ""
            ]

            seen = set()

            for key, value in query.queryItems():
                
                #only add parts to filter if they're in the filter lists
                if (key.startswith("utm_") or key in Tracking_Parameters):
                    continue

                pair = (key, value)

                if pair in seen:
                    continue

                seen.add(pair)

                clean_query.addQueryItem(key, value)

        qurl.setQuery(clean_query)

        if not navlink: #only run this when not sanitising navigation links. Bookmarks need agressive normalisation but doing so for navlinks might break some sites
            host = qurl.host()
            if host.startswith("www."):
                qurl.setHost(host[4:])

            # normalise path
            path = qurl.path()
            if path.endswith("/") and path != "/":
                path = path.rstrip("/")
            if path == "":
                path = "/"

            qurl.setPath(path)

            qurl.setFragment("")
        
        return qurl.toString()
    


class AdInterceptor(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        
        source_url = info.firstPartyUrl().toString()
        
        # Pass the actual resource type from Qt
        if not is_url_safe(url, source_url, info.resourceType()):
            print(f"Midnight Shield: BLOCKED {url}")
            info.block(True)


class CosmeticBlocker:
    @staticmethod
    def inject_css(browser):
        url = browser.url().toString()
        css_rules = get_cosmetic_filters(url)
        
        # Safely convert the CSS payload to a valid JSON-encoded JavaScript string literal
        safe_css_rules = json.dumps(css_rules)
        
        js_payload = f"""
        try {{
            (function() {{
                const inject = () => {{
                    const target = document.head || document.documentElement;
                    if (!target) return;
                    
                    let style = document.getElementById('midnight-cosmetic-shield');
                    if (!style) {{
                        style = document.createElement('style');
                        style.id = 'midnight-cosmetic-shield';
                        target.appendChild(style);
                    }}
                    // safe_css_rules already contains outer quotes due to json.dumps
                    style.textContent = {safe_css_rules}; 
                }};

                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', inject);
                }} else {{
                    inject();
                }}
            }})();
        }} catch (err) {{
            console.error("Midnight Shield Cosmetic Error: ", err.name, " ", err.message);
        }}
        """
        browser.page().runJavaScript(js_payload)


class ScriptletBlocker:
    @staticmethod
    def inject_scriptlets(browser):
        url = browser.url().toString()
        script_code = get_scriptlets(url)
        if script_code:
            # Scriptlets are raw JS designed to neuter ad-logic
            browser.page().runJavaScript(script_code)
            print(f"Injected scriptlets for {url}")


class EVAdInterceptor():
    @staticmethod
    def deployPayload(browser, profile):
        try:
            with open(f"{srcSourceDir}/Javascript_Executables/embeddedadblocker.js", 'r', encoding='utf-8') as f:
                js_code = f.read()
        except IOError as e:
            print(f"Error reading embeddedadblocker javascript file")
            js_code = ""
        #Deploy JS payload for script blocking
        script = QWebEngineScript()
        script.setSourceCode(js_code)
        script.setName("EVAdIntercept_Payload")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(True)


        try:
            with open(f"{srcSourceDir}/Javascript_Executables/youtubeBlocker.js", 'r', encoding='utf-8') as f:
                ytb_txt = f.read()
        except IOError as e:
            print(f"Error reading youtube adblocker javascript file")
            ytb_txt = ""
        ytbScript = QWebEngineScript()
        ytbScript.setSourceCode(ytb_txt)
        ytbScript.setName("Youtube_Script_Blocker")
        ytbScript.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        ytbScript.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        ytbScript.setRunsOnSubFrames(True)

        #Add to the page's script collection
        #browser.page().scripts().clear()
        #profile.scripts?
        profile.scripts().insert(script)
        profile.scripts().insert(ytbScript)