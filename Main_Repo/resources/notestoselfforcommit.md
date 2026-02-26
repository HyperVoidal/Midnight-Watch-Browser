# NOTES TO SELF

### libAdblockPlus:
libAdblockPlus fails to effectively start because it's four years old and hasn't updated it's repositories since github phased out systems for username/password authentication. I attempted various workarounds to implement the missing wrapper objects of GYP and GoogleTests, but the systems were so outdated (the GYP alone was only compatible with Python 2.7 and below) that nothing could work properly. Considering the outdated installations, impossible building and the knowledge that no further updates would be made, I decided to abandon libAdblockPlus

### Alternative Options:
- adblock-python: high performance rust-based adblocker with python bindings, installable through PIP as a python library
- braveblock: The Brave Browser ad blocking logic implemented as a python library and installable through PIP
- adblockparser: Pure python easylist adblocking rules, even simpler to use but slower than the other two, installable through PIP as a python library

Used adblock python
Found and implemented youtube adblocker that I am now using as a JS injection in order to ensure that ads can be continually blocked on different sites
Found new system using a nodejs import that may be superior to all of my systems combined, however it will need some time before I can implement it and thus I will commit before attempting so I have a save point to restore to in case of catastrophic error.

### ActionToggles
The actiontoggles json is designed as a basic settings list, currently including encrypted connection options and the level of cookie sensitivity for outputs (will also influence which ones are kept). This will evolve into a full settings menu over time, but currently the values can only be adjusted from within the actionToggles json file itself.

## HUGE PATCH
Massive bugfix by updating the main.py function:

"""
        browser = QWebEngineView()
        new_page = QWebEnginePage(self.profile, browser)
        browser.setPage(new_page)
        browser.setUrl(qurl)
"""

The added two middle lines link the browser variable to the self.profile class where they previously were seperate, meaning that the browser tab objects and everything within them finally update to perform expected tasks. Adblocker has improved in effectiveness by a factor of approximately 1.5x, extensionmanager now appears to be functional (needs further testing) and the in-development cookie system became able to read the inbound cookies from websites.


For reference, the cookie system is an attempt to create a more user-centric design for a cookie tracker blocker. When complete (as it currently is not), the system will grab all inbound cookies and cache them, listing all unique cookies in a GUI alongside the ID, domain, value, and a prediction of it's usage based on the previous three. Users can then make decisions as to which ones to keep and remove. This allows for user-centric preservation of things like login data or session data on certain websites, but the selective blocking and removal of others. If the user simply doesn't open the GUI or interact with accept/denying cookies, all the cookies will never be integrated and thus the entire website will still remain cookie-blocked as the requested ones are simply moved to a cache before being deleted immediately.