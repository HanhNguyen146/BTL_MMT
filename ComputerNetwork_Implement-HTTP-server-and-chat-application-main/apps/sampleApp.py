import os
import json
import socket
import requests
import datetime
from daemon.weaprous import WeApRous

app = WeApRous()

# --- Cấu hình ---
BACKEND_URL = "http://127.0.0.1:8080"  # proxy sẽ trỏ backend.local -> 127.0.0.1:9000
WWW_DIR = os.path.join(os.path.dirname(__file__), "www")
PEERS_CACHE_FILE =os.path.join("db", "peers_cache.json") 
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
    """
    Gửi tin nhắn từ web (sender → to_peer).
    Dù backend hay P2P, hệ thống sẽ lưu tin vào file riêng của từng peer:
      - db/<sender>_messages.json (ghi lại tin đã gửi)
      - db/<to_peer>_messages.json (ghi lại tin nhận dự kiến)
    """
    try:
        data = json.loads(body)
        sender = data.get("from")
        to_name = data.get("to")
        message = data.get("message", "")
        print(f"[SampleApp] Send from {sender} → {to_name}: {message}")

        # ✅ Lưu log ngay vào file của sender (đang gửi)
        save_peer_message(sender, f"To {to_name}: {message}", "send")

        # --- Ưu tiên gửi qua backend ---
        try:
            r = requests.post(f"{BACKEND_URL}/send-peer", json=data, timeout=3)
            if r.status_code == 200:
                print(f"[SampleApp] ✅ Sent via backend")
                save_peer_message(to_name, f"From {sender}: {message}", "recv")
                return {"status": "backend", "reply": r.text}
            else:
                raise Exception(f"Backend trả lỗi {r.status_code}")
        except Exception as e:
            print(f"[SampleApp] ⚠️ Backend error: {e} → fallback P2P")

            # --- fallback: gửi trực tiếp nếu có peer cache ---
            if to_name in PEERS_CACHE:
                ip, port = PEERS_CACHE[to_name]
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect((ip, int(port)))
                    s.sendall(f"[Direct from {sender}] {message}".encode("utf-8"))
                    s.close()
                    print(f"[SampleApp] ✅ Sent direct to {ip}:{port}")
                    save_peer_message(to_name, f"From {sender}: {message}", "recv")
                    return {"status": "direct", "target": f"{ip}:{port}"}
                except Exception as e2:
                    print(f"[SampleApp] ❌ Direct send failed: {e2}")
                    save_peer_message(sender, f"To {to_name}: {message} (send failed)", "failed")
                    return {"error": str(e2)}
            else:
                save_peer_message(sender, f"To {to_name}: {message} (no peer info)", "failed")
                return {"error": f"No cached info for peer {to_name}"}

    except Exception as e:
        print(f"[ERROR] send_peer: {e}")
        return {"error": str(e)}




@app.route("/broadcast-peer", methods=["POST"])
def broadcast(body):
    try:
        data = json.loads(body)
        msg = data.get("message", "")
        sender = data.get("from", "unknown")

        print(f"[SampleApp] Broadcast from {sender}: {msg}")
        success = []

        for name, (ip, port) in PEERS_CACHE.items():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((ip, int(port)))
                s.sendall(f"[Broadcast from {sender}] {msg}".encode("utf-8"))
                s.close()
                success.append(name)
                save_peer_message(name, f"From {sender} (broadcast): {msg}", "recv")
            except Exception as e:
                print(f"[WARN] Broadcast error {name}: {e}")

        # Ghi lại vào file của sender
        save_peer_message(sender, f"Broadcasted: {msg}", "send")

        return {"status": "ok", "sent_to": success}
    except Exception as e:
        return {"error": str(e)}



@app.route("/get-messages", methods=["GET"])
def get_messages(req):
    """
    API: /get-messages?peer=app1
    Trả về nội dung file db/<peer>_messages.json
    """
    import urllib.parse
    params = urllib.parse.parse_qs(urllib.parse.urlparse(req.path).query)
    peer = params.get("peer", [""])[0].strip()

    if not peer:
        return {"error": "Missing peer parameter"}

    file_path = os.path.join("db", f"{peer}_messages.json")
    if not os.path.exists(file_path):
        return {"peer": peer, "messages": []}

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {"peer": peer, "messages": data}

    
# ==========================================================
# 🔹 Lưu log chat cục bộ (đọc lại sau khi restart)
# ==========================================================
def save_peer_message(peer_name, msg, direction="recv"):
    """
    Lưu tin nhắn của từng peer vào file riêng:
        db/<peer_name>_messages.json
    direction: 'recv' | 'send' | 'pending' | 'failed'
    """
    db_dir = "db"
    os.makedirs(db_dir, exist_ok=True)
    file_path = os.path.join(db_dir, f"{peer_name}_messages.json")

    try:
        messages = []
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                messages = json.load(f)
                if not isinstance(messages, list):
                    messages = []

        messages.append({
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "direction": direction,
            "content": msg
        })

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)

        print(f"[ChatLog] 💾 Saved message in {peer_name}_messages.json ({direction})")
    except Exception as e:
        print(f"[ChatLog] ⚠️ Error saving {peer_name}_messages.json: {e}")

# ==========================================================
#  Chạy ứng dụng
# ==========================================================
if __name__ == "__main__":
    load_cache()
    print("[SampleApp] Web UI running at http://127.0.0.1:8000 (through proxy 8080)")
    app.prepare_address("127.0.0.1", 8000)
    app.run()
