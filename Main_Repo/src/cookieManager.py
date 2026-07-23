from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineCookieStore
from PySide6.QtCore import QDateTime


class CookieManager:    
    def __init__(self, profile, sensitivity, cookieAutoHandler):
        self.store = profile.cookieStore()
        #Storing latest versions of unique cookies for reference
        self.pending_cookies = {}
        self.Sensitivity = sensitivity #determines how defensive/sensitive the cookie prediction system is
        self.cookieAutoHandler = cookieAutoHandler
        # Start the filter immediately
        self.setup_filter()
    
    def updateSensitivity(self, newSensitivity):
        self.Sensitivity = int(newSensitivity)
        print(f"Cookie sensitivity updated to: {self.Sensitivity}")
    
    def updateHandler(self, handler):
        self.cookieAutoHandler = int(handler)
        print(f"Cookie auto-handler updated to: {self.cookieAutoHandler}")


    def setup_filter(self):
        self.store.setCookieFilter(self.filter_logic)

    def filter_logic(self, request):
        # 'request' is a FilterRequest object
        # It has: origin (QUrl), firstPartyUrl (QUrl), and outOfLine (bool)
        
        domain = request.origin.host().lower()

        #security layer 1 - third party cookies. There are only a few niche use cases like embedded players remembering account data from your browser, but that 
        #also provides an addiional attack vector for tracking and fingerprinting, so we block all third-party cookies by default. Regardless of the usefulness,
        #fingerprinting is still fingerprinting, especially without consent, and this is by no means website-breaking.
        if self.Sensitivity > 1:
            if request.thirdParty:
                print(f"Blocked third-party cookie from: {request.origin.toString()}")
                return False  # Deny
        
        #security layer 2 - domain reputation.
        # Since we can't see the 'name' in the filter, 
        # we filter based on the reputation of the domain
        if self.Sensitivity == 2 or self.Sensitivity == 3:
            return False  # Block all
            
        if self.Sensitivity == 1:
            # Check if the domain is known for ads/tracking
            if any(x in domain for x in ["doubleclick", "google-analytics", "facebook", "amazon-adsystem"]):
                return False
                
        return True

    def cookieInterceptor(self, request):
        origin = request.origin.toString()

        if origin not in self.pending_cookies:  
            self.pending_cookies[origin] = []

        return True
    
    def refresh_cookie_list(self):
        return self.pending_cookies


    def on_cookie_added(self, cookie, hostDomain):
        name = cookie.name().data().decode(errors='ignore')
        domain = cookie.domain()
        
        #Create a unique key for deduplication
        cookie_id = f"{domain}|{name}"
        
        #Add or update the entry
        self.pending_cookies[cookie_id] = {
            "name": name,
            "objectCode": cookie,
            "domain": domain,
            "value": cookie.value().data().decode(errors='ignore'),
            "prediction": self.predict_use_case(name, domain, cookie, hostDomain),
            "is_secure": cookie.isSecure()
        }

        print(name, domain, self.predict_use_case(name, domain, cookie, hostDomain))
        
        # Debug print (filtered)
        #print(f"Updated {name} [{self.pending_cookies[cookie_id]['prediction']}]")
        if self.Sensitivity == 0:
            #If the cookie passes all checks, allow the cookie to save automatically
            if self.cookieAutoHandler:
                self.acceptCookie(cookie_id)
                return
            else:
                pass
        elif self.Sensitivity == 1:
            try:
                prediction = self.pending_cookies[cookie_id]["prediction"]
                if prediction in ["Advertising", "Analytics (Tracking)", "Suspicious"]:
                    self.cookieEVAPORATOR(cookie_id)
                else:
                    #If the cookie passes all checks, allow the cookie to save automatically
                    if self.cookieAutoHandler:
                        self.acceptCookie(cookie_id)
                    else:
                        pass
            except RuntimeError:
                return
        elif self.Sensitivity == 2:
            try:
                prediction = self.pending_cookies[cookie_id]["prediction"]
                if prediction in ["Functional/Preference", "Advertising", "Analytics (Tracking)", "Suspicious"]:
                    self.cookieEVAPORATOR(cookie_id)
                else:
                    #If the cookie passes all checks, allow the cookie to save automatically
                    if self.cookieAutoHandler:
                        self.acceptCookie(cookie_id)
                    else:
                        pass
            except RuntimeError:
                return
        else:
            try:
                self.cookieEVAPORATOR(cookie_id)
            except RuntimeError:
                return


    def predict_use_case(self, name, domain, cookie, hostDomain):
        n = name.lower()
        d = domain.lower()
        
        if any(x in n for x in ["consent", "sess", "auth", "login", "csrf", "token", "verification"]):
            return "Essential (Login/Consent)"
        
        if "aws" in n or "balancer" in n:
            return "Infrastructure (Performance)"
        
        if any(x in n for x in ["_ga", "_gid", "metrics", "stats", "amplitude"]):
            return "Analytics (Tracking)"
        
        if any(x in d for x in ["doubleclick", "ads", "adnxs", "facebook", "amazon-adsystem"]):
            return "Advertising"
        
        #passes guard clauses, therefore use predictive measures on the existing cookie data
        prediction_score = 0

        if not cookie.isSessionCookie():
            prediction_score += 1
        
        days = QDateTime.currentDateTime().daysTo(cookie.expirationDate())
        if days > 30:
            prediction_score += 1

        elif days > 365:
            prediction_score += 2

        elif days > 365 * 5:
            prediction_score += 3
        else:
            prediction_score -= 1


        if not cookie.isSecure():
            prediction_score += 3
        
        if not self.same_site(d, hostDomain):
            prediction_score += 2

        if len(cookie.value().data()) > 200:
            prediction_score += 1

        tracking_prefixes = [
            "_ga",
            "_gid",
            "_fbp",
            "_gcl",
            "_uet",
            "_pin",
            "_ttp"
        ]
        if any(n.startswith(x) for x in tracking_prefixes):
            prediction_score += 4

        if not cookie.isHttpOnly():
            prediction_score += 1

        if prediction_score >= 5: #Placeholder value, not sure what else to add for suspicious cookie additions 
            return "Suspicious"
        else:
            return "Functional/Preference"
    

    def cookieEVAPORATOR(self, cookieID):
        if cookieID in self.pending_cookies:
            #Retrieve the stored QNetworkCookie object
            cookie_obj = self.pending_cookies[cookieID]["objectCode"]
            self.store.deleteCookie(cookie_obj)
            
            # Remove from internal tracking
            del self.pending_cookies[cookieID]
            print(f"Evaporated: {cookieID}")

    def clear_all_cookies(self):
        """Delete every tracked cookie from both the WebEngine store and the app's in-memory cache."""
        if hasattr(self, "store") and self.store is not None:
            try:
                self.store.deleteAllCookies()
            except Exception as exc:
                print(f"Cookie mass delete failed in store: {exc}")

        self.pending_cookies.clear()
        print("Cleared all tracked cookies from the local cookie manager")

    def acceptCookie(self, cookieID):
        if cookieID in self.pending_cookies:
            del self.pending_cookies[cookieID]
            print(f"Accepted: {cookieID}")


    def same_site(self, cookie_domain, host_domain):
        cookie_domain = cookie_domain.lstrip(".").lower()
        host_domain = host_domain.lower()

        return (
            host_domain == cookie_domain
            or host_domain.endswith("." + cookie_domain)
        )