import os
import json
import socket
import requests
from daemon.weaprous import WeApRous

app = WeApRous()

# --- Cấu hình ---
BACKEND_URL = "http://127.0.0.1:8080"  # proxy sẽ trỏ backend.local -> 127.0.0.1:9000
WWW_DIR = os.path.join(os.path.dirname(__file__), "www")
PEERS_CACHE_FILE = "peers_cache.json"
PEERS_CACHE = {}
# ==========================================================
#  Hỗ trợ lưu/đọc cache để dùng lại sau khi restart
# ==========================================================
def load_cache():
    global PEERS_CACHE
    if os.path.exists(PEERS_CACHE_FILE):
        try:
            with open(PEERS_CACHE_FILE, "r", encoding="utf-8") as f:
                PEERS_CACHE = json.load(f)
                print(f"[Cache] Loaded {len(PEERS_CACHE)} peers from cache file.")
        except Exception as e:
            print(f"[Cache] Error reading cache: {e}")

def save_cache():
    try:
        with open(PEERS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(PEERS_CACHE, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Cache] Error saving cache: {e}")

# ==========================================================
#  Phục vụ các trang HTML tĩnh (index, login, submit-info)
# ==========================================================
def serve_file(filename):
    path = os.path.join(WWW_DIR, filename)
    if not os.path.exists(path):
        return f"<h1>404</h1><p>{filename} not found</p>"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@app.route("/", methods=["GET"])
def home(_):
    return serve_file("index.html")

@app.route("/login", methods=["GET"])
def login_page(_):
    return serve_file("login.html")

@app.route("/submit-info", methods=["GET"])
def submit_info_page(_):
    return serve_file("submit-info.html")

# ==========================================================
#  API gọi tới backend (Tracker)
# ==========================================================
@app.route("/add-list", methods=["POST"])
def add_list(body):
    try:
        data = json.loads(body)
        print(f"[SampleApp] Forward /add-list to backend: {data}")
        r = requests.post(f"{BACKEND_URL}/add-list", json=data, timeout=3)
        print(f"[Backend] -> {r.status_code} {r.text[:100]}")
        return {"status": r.status_code, "backend_reply": r.text}
    except Exception as e:
        print(f"[WARN] Backend unreachable: {e}")
        return {"error": f"Backend unreachable: {e}"}
    
@app.route("/get-list", methods=["GET"])
def get_peer_list(_):
    try:
        print("[SampleApp] Forward /get-list to backend")
        r = requests.get(f"{BACKEND_URL}/get-list", timeout=3)
        data = r.json()
        for p in data.get("list", []):
            if all(k in p for k in ("user", "host", "port")):
                PEERS_CACHE[p["user"]] = (p["host"], p["port"])
        save_cache()
        print(f"[Cache] Updated peers: {list(PEERS_CACHE.keys())}")
        return data
    except Exception as e:
        print(f"[WARN] Backend down: {e}. Using cache.")
        return {"error": str(e), "cached": list(PEERS_CACHE.keys())}

@app.route("/connect-peer", methods=["POST"])
def connect_peer(body):
    """
    API trung gian: nhận request connect-peer từ web hoặc peer,
    sau đó forward đến backend (9000) qua proxy.
    """
    try:
        data = json.loads(body)
        print(f"[SampleApp] Forward /connect-peer → backend: {data}")

        # forward qua proxy 8080 → backend.local (9000)
        r = requests.post(f"{BACKEND_URL}/connect-peer", json=data, timeout=3)
        return {"status": "backend", "result": r.text}
    except Exception as e:
        print(f"[ERROR] connect-peer: {e}")
        return {"error": str(e)}

@app.route("/send-peer", methods=["POST"])
def send_peer(body):
    try:
        data = json.loads(body)
        sender = data.get("from")
        to_name = data.get("to")
        message = data.get("message", "")
        print(f"[SampleApp] Send from {sender} to {to_name}")

        # --- Ưu tiên gửi qua backend ---
        try:
            # Gửi qua backend
            r = requests.post(f"{BACKEND_URL}/send-peer", json=data, timeout=3)
            if r.status_code == 200:
                print(f"[SampleApp] ({r.status_code})")
                save_chat_log(sender, to_name, message, "backend")
                return {"status": "backend", "reply": r.text}
            else:
                raise Exception(f"Backend trả lỗi {r.status_code}")
        except Exception as e:
            print(f"[SampleApp]  Backend error ({e}), fallback P2P")

            # --- Nếu backend không dùng được, gửi trực tiếp ---
            if to_name in PEERS_CACHE:
                ip, port = PEERS_CACHE[to_name]
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect((ip, int(port)))
                    s.sendall(f"[Direct from Web] {message}".encode("utf-8"))
                    s.close()
                    print(f"[SampleApp] Direct {ip}:{port}")
                    save_chat_log(sender, to_name, message, "direct")
                    return {"status": "direct", "target": f"{ip}:{port}"}
                except Exception as e2:
                    print(f"[SampleApp] P2P error: {e2}")
                    return {"error": str(e2)}
            else:
                print("[SampleApp] No peer info in cache")
                return {"error": "peer not found"}

    except Exception as e:
        print(f"[ERROR] send_peer: {e}")
        return {"error": str(e)}


@app.route("/broadcast-peer", methods=["POST"])
def broadcast(body):
    try:
        data = json.loads(body)
        msg = data["message"]
        sender = data["from"]
        success = []
        for name, (ip, port) in PEERS_CACHE.items():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((ip, int(port)))
                s.sendall(f"[Broadcast from {sender}] {msg}".encode("utf-8"))
                s.close()
                success.append(name)
            except Exception as e:
                print(f"[WARN] Broadcast error {name}: {e}")
        return {"status": "ok", "sent_to": success}
    except Exception as e:
        return {"error": str(e)}

@app.route("/get-log-messages", methods=["GET"])
def get_logs(_):
    try:
        with open("chat_log.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"logs": data}
    except Exception:
        return {"logs": []}

    
# ==========================================================
# 🔹 Lưu log chat cục bộ (đọc lại sau khi restart)
# ==========================================================
def save_chat_log(sender, receiver, message, via):
    log_file = "chat_log.json"
    try:
        # Đọc log cũ
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []

        # Thêm dòng mới
        logs.append({
            "from": sender,
            "to": receiver,
            "message": message,
            "via": via
        })

        # Ghi lại file
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Can not save log: {e}")

# ==========================================================
#  Chạy ứng dụng
# ==========================================================
if __name__ == "__main__":
    load_cache()
    print("[SampleApp] Web UI running at http://127.0.0.1:8000 (through proxy 8080)")
    app.prepare_address("127.0.0.1", 8000)
    app.run()
