import threading
import socket
import time
import json
import requests

# ========================================================
# HÀM START_PEER (Lấy từ testp2p.py)
# ========================================================
def start_peer(name, port):
    
    # --- 1. VAI TRÒ SERVER (Lắng nghe ở 'port') ---
    def listener():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Ràng buộc vào cổng được chỉ định (ví dụ: 9001)
            s.bind(("127.0.0.1", port))
        except OSError as e:
            print(f"[{name}] (Vai tro Client) LOI FATAL: Port {port} da duoc su dung. {e}")
            return
            
        s.listen(5)
        print(f"[{name}] (Vai tro Client) Dang lang nghe tin nhan TCP o 127.0.0.1:{port}")
        
        while True:
            try:
                conn, addr = s.accept()
                data = conn.recv(1024).decode()
                if data:
                    print(f"[{name}] (Vai tro Client) Nhan duoc tin: {data}")
                conn.close()
            except Exception as e:
                print(f"[{name}] (Vai tro Server) Loi listener: {e}")

    # Chạy luồng listener
    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.5) # Chờ listener sẵn sàng

    # --- 2. VAI TRÒ CLIENT (Gọi đến Tracker 9000) ---
    TRACKER_URL = "http://127.0.0.1:8080"

    # Đăng ký (register) với Tracker 9000
    try:
        r_add = requests.post(f"{TRACKER_URL}/add-list",
                          json={"user": name, "item":"active", "host":"127.0.0.1","port":port})
        print(f"[{name}] (Vai tro Client) Dang ky voi Tracker 9000: {r_add.text}")
    except requests.exceptions.ConnectionError:
        print(f"[{name}] (Vai tro Client) LOI: Khong ket noi duoc voi Tracker 9000.")
        print("          Ban da chay 'py start_backend.py --server-port 9000' chua?")
        return 

    # Lấy danh sách
    r_get = requests.get(f"{TRACKER_URL}/get-list")
    try:
        print(f"[{name}] (Vai tro Client) Lay danh sach list: {r_get.json()}")
    except requests.exceptions.JSONDecodeError:
        print(f"[{name}] (Vai tro Client) LOI khi lay list: Server tra ve non-JSON: {r_get.text[:100]}...")

    # # --- AUTO CONNECT ---
    # try:
    #     data = r_get.json()
    #     peer_list = data.get("list", [])
    #     for peer in peer_list:
    #         peer_name_other = peer.get("user")
    #         if peer_name_other and peer_name_other != name:
    #             resp = requests.post(f"{TRACKER_URL}/connect-peer", json={"peer": peer_name_other})
    #             print(f"[{name}] (Auto-connect) Ket noi voi '{peer_name_other}': {resp.text}")
    # except Exception as e:
    #     print(f"[{name}] (Auto-connect) Loi: {e}")


    # --- PHẦN BỔ SUNG: GỌI GET /login (Theo yêu cầu của bạn) ---
    print(f"[{name}] (Vai tro Client) Dang goi GET /login de lay noi dung HTML...")
    r_login = requests.get(f"{TRACKER_URL}/login")
    
    # Phải dùng .text, KHÔNG dùng .json()
    print(f"[{name}] (Vai tro Client) Da nhan duoc {len(r_login.text)} bytes HTML tu /login.")
    # In ra 100 ký tự đầu tiên của trang HTML
    #print(f"          Noi dung HTML (100 ky tu dau): {r_login.text[:100]}...")
    # --- KẾT THÚC PHẦN BỔ SUNG ---


    print(f"--- [{name}] da khoi dong xong. Dang chay... ---")
    while True:
        time.sleep(5)

    # --- FALLBACK: đọc file db khi backend tắt ---
import json, os

PEER_CONNECTION_FILE = os.path.join("db", "peer_connections.json")

if os.path.exists(PEER_CONNECTION_FILE):
    try:
        with open(PEER_CONNECTION_FILE, "r", encoding="utf-8") as f:
            connections = json.load(f)
        if os.name in connections:
            for peer in connections[os.name]:
                peer_name = peer["peer"]
                ip = peer["ip"]
                port = peer["port"]
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect((ip, int(port)))
                    s.sendall(f"[AutoReconnect] Hello {peer_name} from {os.name}".encode("utf-8"))
                    s.close()
                    print(f"[{os.name}] (Fallback) Reconnected trực tiếp với {peer_name} ({ip}:{port})")
                except Exception as e:
                    print(f"[{os.name}] (Fallback) Không thể kết nối {peer_name}: {e}")
        else:
            print(f"[{os.name}] Không có peer nào trong file {PEER_CONNECTION_FILE}")
    except Exception as e:
        print(f"[{os.name}] Lỗi đọc file {PEER_CONNECTION_FILE}: {e}")
else:
    print(f"[{os.name}] Chưa có file {PEER_CONNECTION_FILE} (chưa từng connect-peer)")
# =========================
# Main
# =========================
if __name__ == "__main__":
    print("--- Khoi chay PEER 'app3' ---")
    start_peer(name="app3", port=9003)