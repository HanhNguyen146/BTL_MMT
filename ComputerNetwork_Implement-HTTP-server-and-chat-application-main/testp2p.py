import threading
import socket
import time
import json
import requests

# =========================
# Backend thread
# =========================
def start_backend():
    from daemon import create_backend
    create_backend("127.0.0.1", 9000)

# =========================
# Peer thread
# =========================
def start_peer(name, port, peer_name=None, message=None):
    # listener
    def listener():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", port))
        s.listen(5)
        print(f"[{name}] Listening on 127.0.0.1:{port}")
        while True:
            conn, addr = s.accept()
            data = conn.recv(1024).decode()
            if data:
                print(f"[{name}] Received: {data}")
            conn.close()

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(1)

    # register to backend
    r = requests.post("http://127.0.0.1:9000/add-list",
                      json={"user": name, "item":"active", "host":"127.0.0.1","port":port})
    print(f"[{name}] Register: {r.text}")

    # connect to peer
    if peer_name:
        r = requests.post("http://127.0.0.1:9000/connect-peer",
                          json={"peer": peer_name})
        print(f"[{name}] Connect-peer: {r.text}")
    r = requests.get("http://127.0.0.1:9000/get-list")
    print(r.json())

    # send private message
    if peer_name and message:
        r = requests.post("http://127.0.0.1:9000/send-peer",
                          json={"from": name, "to": peer_name, "message": message})
        print(f"[{name}] Send-peer response: {r.text}")

    while True:
        time.sleep(1)

# =========================
# Main test
# =========================
if __name__ == "__main__":
    # start backend
    threading.Thread(target=start_backend, daemon=True).start()
    time.sleep(1)

    # start peers
    threading.Thread(target=start_peer, args=("app1", 9101, "app2", "Hello app2!"), daemon=True).start()
    threading.Thread(target=start_peer, args=("app2", 9102), daemon=True).start()

    # keep main alive
    while True:
        time.sleep(1)
