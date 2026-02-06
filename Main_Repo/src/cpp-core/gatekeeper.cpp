#include <QString>
#include <iostream>

extern "C" {
    int verify_url_safe(const char* url) {
        QString q_url = QString::fromUtf8(url);
        
        // Block common ad-server patterns
        if (q_url.contains("ads.") || 
            q_url.contains("telemetry") || 
            q_url.contains("analytics")) {
            return 0; 
        }
        
        return 1;
    }
}