#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
start_sampleapp
~~~~~~~~~~~~~~~~~

This module provides a sample RESTful web application using the WeApRous framework.

It defines basic route handlers and launches a TCP-based backend server to serve
HTTP requests. The application includes a login endpoint and a greeting endpoint,
and can be configured via command-line arguments.
"""
import os
import json
import socket
import argparse
import requests
import datetime
from daemon.weaprous import WeApRous
WWW_DIR = os.path.join(os.path.dirname(__file__), "www")

PORT = 8000  # Default port

app = WeApRous()

# --- Cấu hình ---
BACKEND_URL = "http://127.0.0.1:9000"  # proxy sẽ trỏ backend.local -> 127.0.0.1:9000
WWW_DIR = os.path.join(os.path.dirname(__file__), "www")
PEERS_CACHE_FILE = os.path.join("db", "peers_cache.json") 
LOG_FILE = os.path.join("db", "chat_log.json")
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
#  Phục vụ các trang HTML tĩnh (index, login, submit-info)
# ==========================================================
def serve_file(filename):
   return

@app.route("/", methods=["GET"])
@app.route("/index", methods=["GET"])
@app.route("/index.html", methods=["GET"])
def home(_):
    print("HELLLOOOOOOOOOOOOOOOOOOOO")
    try:
        r = requests.get(f"{BACKEND_URL}/", timeout=3)
        # Trả về nội dung HTML thô
        return r.text 
    except Exception as e:
        print(f"[SampleApp] Lỗi GET /: {e}")
        return f"<h1>503 Service Unavailable</h1><p>Không thể kết nối đến Proxy (8080).</p>"

@app.route("/login", methods=["GET"])
def login_page(_):
    try:
        r = requests.get(f"{BACKEND_URL}/login", timeout=3)
        return r.text
    except Exception as e:
        print(f"[SampleApp] Lỗi GET /login: {e}")
        return f"<h1>503 Service Unavailable</h1><p>Không thể kết nối đến Proxy (8080).</p>"

@app.route("/submit-info", methods=["GET"])
def submit_info_page(_):
    try:
        r = requests.get(f"{BACKEND_URL}/submit-info", timeout=3)
        return r.text
    except Exception as e:
        print(f"[SampleApp] Lỗi GET /submit-info: {e}")
        return f"<h1>503 Service Unavailable</h1><p>Không thể kết nối đến Proxy (8080).</p>"

# ==========================================================
#  API gọi tới backend (Tracker)
# ==========================================================
@app.route("/add-list", methods=["POST"])
def add_list(body):
    """
    Gửi yêu cầu đăng ký peer tới backend (lưu trong peer_connections.json)
    """
    try:
        data_from_client = json.loads(body)
        name = data_from_client.get("user")
        if not name:
            raise ValueError("Missing 'user' in body")

        data_for_backend = {
            "user": name,
            "item": "ONLINE",           # backend sẽ ghi vào status
            "host": app.ip,             # IP của peer (app)
            "port": app.port            # cổng peer đang chạy
        }

        print(f"[SampleApp] Forwarding /add-list → backend: {data_for_backend}")
        r = requests.post(f"{BACKEND_URL}/add-list", json=data_for_backend, timeout=3)
        print(f"[Backend] → {r.status_code} {r.text[:120]}")

        # Phản hồi JSON cho trình duyệt
        return r.json()

    except Exception as e:
        print(f"[WARN] Backend unreachable: {e}")
        return {"error": f"Backend unreachable: {e}"}

@app.route("/get-list", methods=["GET"])
def get_peer_list(_):
    """
    Lấy danh sách peers từ peer_connections.json qua backend
    """
    try:
        print("[SampleApp] Forward /get-list → backend")
        r = requests.get(f"{BACKEND_URL}/get-list", timeout=3)
        data = r.json()

        # backend mới trả: {"list": [{"peer":..., "ip":..., "port":...}, ...]}
        for p in data.get("list", []):
            if all(k in p for k in ("peer", "ip", "port")):
                PEERS_CACHE[p["peer"]] = (p["ip"], p["port"])

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
    Đảm bảo hướng lưu log đúng:
      - Broadcast: chỉ ghi SEND ở người gửi, RECV ở tất cả người nhận.
      - Private: ghi SEND ở người gửi và RECV ở người nhận.
    """
    try:
        data = json.loads(body)
        sender = data.get("from")
        to_name = data.get("to")
        message = data.get("message", "")
        print(f"[SampleApp] Send from {sender} → {to_name}: {message}")

        # ✅ 1️⃣ Broadcast (không chỉ định 'to')
        if not to_name or to_name.lower() in ["all", "broadcast"]:
            # Người gửi: ghi SEND
            save_peer_message(sender, f"Broadcasted: {message}", "send")

            # Gửi đến tất cả peers trong cache (mỗi người nhận ghi RECV)
            for peer_name, (ip, port) in PEERS_CACHE.items():
                if peer_name != sender:
                    save_peer_message(peer_name, f"From {sender} (broadcast): {message}", "recv")
            print(f"[SampleApp] ✅ Broadcast logged for {sender}")
            return {"status": "ok", "type": "broadcast"}

        # ✅ 2️⃣ Gửi riêng (private)
        else:
            # Người gửi: ghi SEND
            save_peer_message(sender, f"To {to_name}: {message}", "send")

            # --- Ưu tiên gửi qua backend ---
            try:
                r = requests.post(f"{BACKEND_URL}/send-peer", json=data, timeout=3)
                if r.status_code == 200:
                    print(f"[SampleApp] ✅ Sent via backend")
                    # Người nhận: ghi RECV
                    save_peer_message(to_name, f"From {sender}: {message}", "recv")
                    return {"status": "backend", "reply": r.text}
                else:
                    raise Exception(f"Backend trả lỗi {r.status_code}")
            except Exception as e:
                print(f"[SampleApp] ⚠️ Backend error: {e} → fallback P2P")

                # --- fallback gửi trực tiếp ---
                if to_name in PEERS_CACHE:
                    ip, port = PEERS_CACHE[to_name]
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.connect((ip, int(port)))
                        s.sendall(f"[Direct from {sender}] {message}".encode("utf-8"))
                        s.close()
                        print(f"[SampleApp] ✅ Sent direct to {ip}:{port}")

                        # Người nhận: ghi RECV
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

        # --- CHỈ LẤY CÁC PEER ĐÃ CONNECT TỪ peer_connections.json ---
        connections_file = os.path.join("db", "peer_connections.json")
        if not os.path.exists(connections_file):
            return {"error": "peer_connections.json not found"}

        with open(connections_file, "r", encoding="utf-8") as f:
            connections = json.load(f)

        # Danh sách kết nối của người gửi
        sender_conn = connections.get(sender, [])

        # Loại bỏ chính nó
        sender_conn = [p for p in sender_conn if p.get("peer") != sender]

        for entry in sender_conn:
            target_peer = entry.get("peer")
            ip = entry.get("ip")
            port = entry.get("port")

            if not ip or not port:
                print(f"[WARN] Missing ip/port for {target_peer}")
                continue

            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((ip, int(port)))
                s.sendall(f"[Broadcast from {sender}] {msg}".encode("utf-8"))
                s.close()

                success.append(target_peer)

                # Log RECV
                save_peer_message(target_peer, f"From {sender} (broadcast): {msg}", "recv")

            except Exception as e:
                print(f"[WARN] Broadcast error {target_peer}: {e}")

        # Log SEND
        save_peer_message(sender, f"Broadcasted: {msg}", "send")

        return {"status": "ok", "sent_to": success}

    except Exception as e:
        return {"error": str(e)}


@app.route("/get-chat-log", methods=["POST"])
def get_chat_log(body):
    """
    API: POST /get-chat-log
    Body: {"peer": "Client2"}
    Trả về JSON lịch sử tin nhắn của peer (đọc db/<peer>_messages.json)
    """
    try:
        data = json.loads(body or "{}")
        peer = (data.get("peer") or "").strip()
        if not peer:
            print("[WARN] /get-chat-log: missing 'peer' in body")
            return {"error": "Missing 'peer' in body"}

        file_path = os.path.join("db", f"{peer}_messages.json")
        print(f"[DEBUG] /get-chat-log read {file_path}")
        if not os.path.exists(file_path):
            return {"peer": peer, "count": 0, "messages": []}

        with open(file_path, "r", encoding="utf-8") as f:
            messages = json.load(f)
            if not isinstance(messages, list):
                messages = []

        print(f"[OK] /get-chat-log → {peer}, {len(messages)} messages")
        return {"peer": peer, "count": len(messages), "messages": messages}

    except Exception as e:
        print(f"[ERROR] /get-chat-log failed: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    # Parse command-line arguments to configure server IP and port
    parser = argparse.ArgumentParser(prog='Backend', description='', epilog='Beckend daemon')
    parser.add_argument('--server-ip', default='0.0.0.0')
    parser.add_argument('--server-port', type=int, default=PORT)
 
    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port
   
    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()
