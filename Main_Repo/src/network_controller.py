from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEngineScript
from engine_bridge import is_url_safe
from pathlib import Path
srcSourceDir = Path(__file__).parent

class AdInterceptor(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        #Get url of subrequest
        url = info.requestUrl().toString()
        
        #Check with gatekeeper
        if not is_url_safe(url):
            print(f"Midnight Shield: BLOCKED {url}")
            info.block(True)

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
        script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
        script.setRunsOnSubFrames(True)

        #Add to the page's script collection
        browser.page().scripts().clear()
        browser.page().scripts().insert(script)