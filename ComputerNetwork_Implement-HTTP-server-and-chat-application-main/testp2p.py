import requests
import socket
import threading
import time
import json

# ====== cấu hình backend ======
BACKEND = "http://127.0.0.1:9000"   # đổi port nếu backend dùng cổng khác

# ====== peer listener (để nhận tin nhắn từ peer khác) ======
def peer_listener(peer_id, ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((ip, port))
    s.listen(5)
    print(f"[{peer_id}]  Listening on {ip}:{port}")
    while True:
        conn, addr = s.accept()
        data = conn.recv(1024).decode()
        print(f"[{peer_id}]  Message from {addr}: {data}")
        conn.close()

# ====== peer main logic ======
def main():
    peer_id = input("Enter your peer ID (peer1, peer2,...): ").strip()
    port = int(input("Enter your listening port (e.g. 9001): "))

    # 1️⃣ Đăng nhập (tùy chọn)
    try:
         r = requests.post(
        f"{BACKEND}/login",
        data={"username": "admin", "password": "password"}  # đúng cặp mà HttpAdapter chấp nhận
    )
         if r.status_code == 200:
            print(f"[LOGIN] ✅ success ({r.status_code})")
         else:
            print(f"[LOGIN] ❌ failed ({r.status_code})")
    except Exception as e:
         print("[ERROR] Cannot login:", e)
         return

    # 2️⃣ Gửi thông tin đăng ký (submit-info)
    try:
        data = {"id": peer_id, "ip": "127.0.0.1", "port": port}
        r = requests.post(f"{BACKEND}/submit-info", json=data)
        print(f"[REGISTER] {r.status_code}: {r.text}")
    except Exception as e:
        print("[ERROR] Cannot submit info:", e)
        return

    # 3️⃣ Khởi động thread listener để nhận tin nhắn
    threading.Thread(target=peer_listener, args=(peer_id, "127.0.0.1", port), daemon=True).start()
    time.sleep(1)

    # 4️⃣ Vòng lặp gửi tin
    while True:
        target = input("\nEnter target peer ID (or 'exit' to quit): ").strip()
        if target.lower() == "exit":
            break

        # Hỏi backend địa chỉ của peer đích
        try:
            r = requests.post(f"{BACKEND}/connect-peer", json={"target_id": target})
            res = json.loads(r.text)
        except Exception as e:
            print("[ERROR] Cannot connect to backend:", e)
            continue

        if res.get("status") != "ok":
            print("[ERROR]", res.get("message"))
            continue

        target_ip, target_port = res["ip"], res["port"]
        msg = input(f"Message to {target}: ")

        # Gửi tin nhắn trực tiếp qua TCP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((target_ip, target_port))
            s.sendall(f"{peer_id}: {msg}".encode())
            s.close()
            print(f"[{peer_id}]  Sent message to {target} ({target_ip}:{target_port})")
        except Exception as e:
            print(f"[{peer_id}]  Cannot send message to {target}: {e}")

    print("Bye")

if __name__ == "__main__":
    main()
