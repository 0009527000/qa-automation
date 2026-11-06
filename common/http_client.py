"""统一的 HTTP 请求封装：base_url、token、超时、日志都在这里收口。"""
import requests

from common.config import REQUEST_TIMEOUT


class ApiClient:
    def __init__(self, base_url, token=None, timeout=REQUEST_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        if token:
            self.session.headers.update({"X-Token": token})

    def request(self, method, path, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        return self.session.request(method, self.base_url + path, **kwargs)

    def close(self):
        self.session.close()
