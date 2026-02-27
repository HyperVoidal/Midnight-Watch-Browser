from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineCookieStore


class CookieManager:    
    def __init__(self, profile, sensitivity):
        self.store = profile.cookieStore()
        #Storing latest versions of unique cookies for reference
        self.pending_cookies = {}
        self.Sensitivity = sensitivity #determines how defensive/sensitive the cookie prediction system is
        # Start the filter immediately
        self.setup_filter()

    def setup_filter(self):
        self.store.setCookieFilter(self.filter_logic)

    def filter_logic(self, request):
        # 'request' is a FilterRequest object
        # It has: origin (QUrl), firstPartyUrl (QUrl), and outOfLine (bool)
        
        domain = request.origin.host().lower()

        #security layer 1 - third party cookies. There are only a few niche use cases like embedded players remembering account data from your browser, but that 
        #also provides an addiional attack vector for tracking and fingerprinting, so we block all third-party cookies by default. Regardless of the usefulness,
        #fingerprinting is still fingerprinting, especially without consent, and this is by no means website-breaking.
        if request.thirdParty:
            print(f"Blocked third-party cookie from: {request.origin.toString()}")
            return False  # Deny
        
        #security layer 2 - domain reputation.
        # Since we can't see the 'name' in the filter, 
        # we filter based on the reputation of the domain
        if self.Sensitivity == 2:
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



    def on_cookie_added(self, cookie):
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
            "prediction": self.predict_use_case(name, domain),
            "is_secure": cookie.isSecure()
        }
        
        # Debug print (filtered)
        #print(f"Updated {name} [{self.pending_cookies[cookie_id]['prediction']}]")
        if self.Sensitivity == 0:
            return self.pending_cookies
        elif self.Sensitivity == 1:
            try:
                for key, value in self.pending_cookies.items():
                    if value["prediction"] == "Functional/Preference" or value["prediction"] == "Advertising" or value["prediction"] == "Analytics (Tracking)":
                        self.cookieEVAPORATOR(key)
            except RuntimeError:
                return
        else:
            try:
                for key, value in self.pending_cookies.items():
                    self.cookieEVAPORATOR(key)
            except RuntimeError:
                return

    def predict_use_case(self, name, domain):
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

        return "Functional/Preference"
    

    def cookieEVAPORATOR(self, cookieID):
        if cookieID in self.pending_cookies:
            #Retrieve the stored QNetworkCookie object
            cookie_obj = self.pending_cookies[cookieID]["objectCode"]
            self.store.deleteCookie(cookie_obj)
            
            # Remove from internal tracking
            del self.pending_cookies[cookieID]
            print(f"Evaporated: {cookieID}")

    def acceptCookie(self, cookieID):
        if cookieID in self.pending_cookies:
            cookie_obj = self.pending_cookies[cookieID]["objectCode"]
            self.store.setCookie(cookie_obj)
            del self.pending_cookies[cookieID]
            print(f"Accepted: {cookieID}")
            print(self.store.loadAllCookies())