from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineScript, QWebEngineUrlRequestJob
from PySide6.QtCore import QUrl, QUrlQuery, QUrlQuery, QBuffer, QIODevice, QByteArray, QFile
from engine_bridge import is_url_safe, get_cosmetic_filters, get_scriptlets
from PySide6.QtWebEngineCore import QWebEngineUrlScheme, QWebEngineUrlSchemeHandler
from pathlib import Path
import os
import json
srcSourceDir = Path(__file__).parent


#This will have to stay it's own class to avoid conflicts with UrlManager systems
class UrlCustomSchemeManager(QWebEngineUrlSchemeHandler):
    def requestStarted(self, job):
        url = job.requestUrl()
        path = url.path().lstrip('/') 
        file_path = os.path.join(srcSourceDir, "ui", path)

        if os.path.exists(file_path):
            #Open the file directly as a QIODevice
            file = QFile(file_path)
            
            #Set the 'job' as the parent so C++ deletes the file object 
            # automatically when the request is done. No Python dicts needed!
            file.setParent(job) 
            
            if file.open(QIODevice.OpenModeFlag.ReadOnly):
                mime = "text/html" if path.endswith(".html") else "image/png"
                if path.endswith(".css"): mime = "text/css"
                
                #Pass the file object directly to reply
                job.reply(mime.encode(), file)
                return

        job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)




class UrlManager():
    def __init__(self):
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
            # Skip unwanted params
            if (
                key.startswith("utm_") or
                key == "si" or
                key == "sei" or
                key in ("fbclid", "gclid") or
                key in ("sg_ss", "ved", "ei", "source", "gs_lcrp", "sca_esv", "iflsig", "uact", "oq", "aqs")
            ):
                continue

            # Only add once
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
    def deployPayload(browser, profile): #function for blocking ads in embedded in videos   
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

        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(True)


        try:
            with open(f"{srcSourceDir}/Javascript_Executables/youtubeBlocker.js", 'r', encoding='utf-8') as f:
                ytb_txt = f.read()
        except IOError as e:
            print(f"Error reading embeddedadblocker javascript file")
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