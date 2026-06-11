
sys = __import__("sys")
toggles = []

if toggles["DNS-over-HTTPS"]:
    #Forces the browser to resolve domains via HTTPS, hiding lookups from the firewall
    sys.argv.append("--built-in-dns-lookup-enabled")
    sys.argv.append("--dns-over-https-templates=https://cloudflare-dns.com")
    print("DNS-over-HTTPS enabled")
else:
    print("DNS-over-HTTPS disabled")

if toggles["Encrypted-Client-Hello"]:
    #Hides the SNI (the website name) during the SSL handshake
    sys.argv.append("--enable-features=EncryptedClientHello")
    print("Encrypted Client Hello enabled")