proxies = {
    'http': 'http://user:pass@proxy_ip:port',
    'https': 'http://user:pass@proxy_ip:port'
}
response = requests.get(url, proxies=proxies)
