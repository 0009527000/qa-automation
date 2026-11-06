"""零依赖的最小被测服务，仅用于让本测试框架 clone 后能立刻跑通。

正式练习时请换成你自己的课程设计 / 开源业务系统，并相应修改 cases/*.yaml。
启动：python mock_server.py   默认监听 http://127.0.0.1:8000
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

USERS = {"test01": "123456"}
ITEMS = [
    {"id": 1, "name": "Java 编程思想"},
    {"id": 2, "name": "软件测试基础"},
    {"id": 3, "name": "Python 自动化测试"},
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_POST(self):
        path = urlparse(self.path).path
        data = self._body()

        if path == "/api/login":
            username = data.get("username")
            password = data.get("password")
            if not username or not password:
                return self._send(400, {"code": 1001, "msg": "用户名或密码为空"})
            if len(str(username)) > 32:
                return self._send(400, {"code": 1003, "msg": "用户名过长"})
            if USERS.get(username) != password:
                return self._send(401, {"code": 1002, "msg": "账号或密码错误"})
            return self._send(200, {"code": 0, "msg": "ok", "token": "demo-token"})

        if path == "/api/order":
            if self.headers.get("X-Token") != "demo-token":
                return self._send(401, {"code": 1004, "msg": "未登录"})
            qty = data.get("quantity")
            if not isinstance(qty, int) or qty <= 0:
                return self._send(400, {"code": 3001, "msg": "数量非法"})
            if qty > 99:
                return self._send(400, {"code": 3002, "msg": "数量超出上限"})
            return self._send(200, {"code": 0, "msg": "ok", "orderId": 10001})

        return self._send(404, {"code": 404, "msg": "not found"})

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/query":
            params = parse_qs(parsed.query)
            keyword = params.get("keyword", [""])[0]
            if not keyword:
                return self._send(400, {"code": 2001, "msg": "keyword 不能为空"})
            if len(keyword) > 50:
                return self._send(400, {"code": 2002, "msg": "keyword 过长"})
            if params.get("debug_slow") == ["1"]:
                # 仅用于演示「优化前后对比」的写法，不是任何真实性能数据
                time.sleep(0.25)
            found = [item for item in ITEMS if keyword in item["name"]]
            return self._send(200, {"code": 0, "data": found, "total": len(found)})

        return self._send(404, {"code": 404, "msg": "not found"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print("mock server listening on http://127.0.0.1:%d" % port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
