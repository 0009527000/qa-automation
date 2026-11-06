"""运行配置，全部可通过环境变量覆盖，便于本地 / CI / 测试环境切换。"""
import os

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.getenv("API_TOKEN", "demo-token")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "5"))

DB_PATH = os.getenv("DB_PATH", "qa_results.sqlite3")

# 设置 MYSQL_HOST 后自动切换到 MySQL（需 pip install PyMySQL 并执行 sql/init.sql）
MYSQL_HOST = os.getenv("MYSQL_HOST", "")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "qa_automation")
