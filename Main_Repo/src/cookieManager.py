from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineCookieStore


class CookieManager:
    def __init__(self, profile, sensitivity):
        self.store = profile.cookieStore()
        #Storing latest versions of unique cookies for reference
        self.pending_cookies = {}
        self.Sensitivity = sensitivity #determines how defensive/sensitive the cookie prediction system is

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
            "domain": domain,
            "value": cookie.value().data().decode(errors='ignore'),
            "prediction": self.predict_use_case(name, domain),
            "is_secure": cookie.isSecure()
        }
        
        # Debug print (filtered)
        print(f"Updated {name} [{self.pending_cookies[cookie_id]['prediction']}]")
        print(self.pending_cookies)

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

        if self.Sensitivity == 0:
            return "Functional/Preference"
        elif self.Sensitivity == 1:
            return "Importance unknown"
        elif self.Sensitivity == 2:
            return "Potential Danger (Importance Unknown)"
        else:
            return "Likely Danger"
