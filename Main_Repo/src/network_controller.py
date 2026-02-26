from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineScript
from engine_bridge import is_url_safe, get_cosmetic_filters, get_scriptlets
from pathlib import Path
srcSourceDir = Path(__file__).parent


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
        
        # Use raw string and triple quotes to avoid Python/JS bracket confusion
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
                    // Use textContent for TrustedHTML compatibility
                    style.textContent = `{css_rules}`; 
                }};

                // If the document is still loading, wait for it
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', inject);
                }} else {{
                    inject();
                }}
            }})();
        }} catch (err) {{
            console.error("Caught Error: ", err.name, " ", err.message);
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
    def deployPayload(browser): #function for blocking ads in embedded in videos   
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

        #Youtube adblocker script deployment, courtesy of https://github.com/kananinirav/Youtube-AdBlocker/blob/master/content.js
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
        browser.page().scripts().clear()
        browser.page().scripts().insert(script)
        browser.page().scripts().insert(ytbScript)