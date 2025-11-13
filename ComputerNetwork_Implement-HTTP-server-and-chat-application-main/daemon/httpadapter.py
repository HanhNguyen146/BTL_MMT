#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist 
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

import os
from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

_global_list = []
peer_list = {}
PEER_CONNECTION_FILE = os.path.join("db", "peer_connections.json")
class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.

    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>` 
    and :class:`Response <Response>` objects for full request lifecycle management.

    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        self.ip = ip
        self.port = port
        self.conn = conn
        self.connaddr = connaddr
        self.routes = routes
        self.request = Request()
        self.response = Response()

    def handle_client(self, conn, addr, routes):
        from . import backend
        import socket
        import os
        import time
        import urllib.parse
    
        import json
        from . import handler_login
        from .session_store import get_user_from_session

        self.conn = conn
        self.connaddr = addr
        req = self.request
        resp = self.response

        msg = b""
        conn.settimeout(0.5)
        deadline = time.time() + 2.0
        raw_req = ""

        handled = False

        while True:
            try:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                msg += chunk
            except socket.timeout:
                if time.time() > deadline:
                    break
                continue

            try:
                raw_req = msg.decode(errors="ignore")
            except Exception:
                raw_req = ""

            header_end = raw_req.find("\r\n\r\n")
            if header_end == -1:
                if time.time() > deadline:
                    break
                else:
                    continue

            headers_part = raw_req[:header_end]
            content_len = 0
            for line in headers_part.split("\r\n"):
                if line.lower().startswith("content-length:"):
                    try:
                        content_len = int(line.split(":", 1)[1].strip())
                    except Exception:
                        content_len = 0
                    break

            body_bytes_len = len(msg) - (header_end + 4)
            if content_len == 0 or body_bytes_len >= content_len:
                break

            if time.time() > deadline:
                break
            deadline = max(deadline, time.time() + 2.0)
            continue

        try:
            raw_req = msg.decode(errors="ignore")
        except Exception:
            raw_req = ""

        try:
            first_line = raw_req.splitlines()[0] if raw_req else ""
        except Exception:
            first_line = ""

        if first_line.startswith("POST /login"):
            print(f"[HttpAdapter] recv bytes={len(msg)} header_end={raw_req.find('\\r\\n\\r\\n')}")

        req.prepare(raw_req, routes)
        
        # Debug: in ra cookie header từ raw request nếu là GET /
        if req.method == "GET" and req.path in ("/", "/index", "/index.html"):
            # Tìm cookie trong raw request
            cookie_line = None
            for line in raw_req.split('\r\n'):
                if line.lower().startswith('cookie:'):
                    cookie_line = line
                    break
            if cookie_line:
                print(f"[HttpAdapter] Raw Cookie header from request: {cookie_line}")
            else:
                print(f"[HttpAdapter] No Cookie header found in raw request")

        if req.path == "/favicon.ico":
            print("[HttpAdapter] Handling /favicon.ico request (204 No Content)")
            headers = (
                "HTTP/1.1 204 No Content\r\n"
                "Connection: close\r\n\r\n"
            )
            conn.sendall(headers.encode())
            conn.close()
            return # Kết thúc ngay lập tức
        
        handler = routes.get((req.method, req.path)) 
        
        if handler:
            print(f"[HttpAdapter] Found WeApRous route: {handler.__name__} for {req.method} {req.path}")
            
            # Kiểm tra authentication cho các route cần đăng nhập
            if req.method == "GET" and req.path in ("/", "/index", "/index.html"):
                # Debug: in ra raw request headers để kiểm tra cookie
                print(f"[HttpAdapter] GET / - Raw request headers:")
                if req.headers:
                    for key, value in req.headers.items():
                        if 'cookie' in key.lower():
                            print(f"  {key}: {value}")
                
                auth_val = ""
                try:
                    print(f"[HttpAdapter] GET / cookies dict: {req.cookies}")
                    print(f"[HttpAdapter] GET / cookies type: {type(req.cookies)}")
                    if req.cookies:
                        auth_val = req.cookies.get("auth", "")
                        if isinstance(auth_val, str):
                            auth_val = auth_val.lower()
                    print(f"[HttpAdapter] GET / auth_val: '{auth_val}'")
                except Exception as e:
                    import traceback
                    print(f"[HttpAdapter] Error reading cookies: {e}")
                    print(f"[HttpAdapter] Traceback: {traceback.format_exc()}")
                    auth_val = ""
                
                if auth_val != "true":
                    # Chưa đăng nhập, trả về 401
                    body = "<h1>401 Unauthorized</h1><p>Login required. <a href=\"/login\">Login</a></p>"
                    headers = ("HTTP/1.1 401 Unauthorized\r\n"
                               "Content-Type: text/html; charset=utf-8\r\n"
                               "Content-Length: {}\r\n"
                               "Connection: close\r\n"
                               "\r\n").format(len(body))
                    conn.sendall(headers.encode() + body.encode())
                    conn.close()
                    return
            
            try:
                # Lấy body cho POST/PUT
                body = ""
                if req.method in ("POST", "PUT"):
                    header_end = raw_req.find("\r\n\r\n")
                    if header_end != -1:
                        content_len = 0
                        for line in raw_req[:header_end].split("\r\n"):
                            if line.lower().startswith("content-length:"):
                                content_len = int(line.split(":", 1)[1].strip())
                                break
                        if content_len > 0:
                            start = header_end + 4
                            body_bytes = msg[start:start + content_len]
                            body = body_bytes.decode("utf-8", errors="ignore")
                
                # *** GỌI HÀM CỦA BẠN (VÍ DỤ: home(), login_page(), add_list()) ***
                # Logic (ví dụ: print("HELLLOO...")) của bạn sẽ chạy ở đây
                # Truyền request object vào handler nếu handler cần cookie
                # Tạm thời lưu req vào handler context để có thể truy cập
                import threading
                threading.current_thread().request_obj = req
                print(f"[HttpAdapter] Saved request object to thread. Cookies: {req.cookies if req.cookies else 'None'}")
                result = handler(body) 

                # Xử lý kết quả trả về (HTML hoặc JSON)
                if isinstance(result, dict): # Nếu là JSON
                    body_resp = json.dumps(result, ensure_ascii=False)
                    headers = f"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {len(body_resp.encode('utf-8'))}\r\nConnection: close\r\n\r\n"
                    conn.sendall(headers.encode() + body_resp.encode('utf-8'))
                else: # Nếu là HTML (string)
                    body_resp = result.encode("utf-8")
                    headers = f"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(body_resp)}\r\nConnection: close\r\n\r\n"
                    conn.sendall(headers.encode() + body_resp)
                
                conn.close()
                return # Đã xử lý xong bằng WeApRous
            
            except Exception as e:
                # Xử lý lỗi nếu hàm handler (ví dụ: home()) của bạn bị lỗi
                print(f"[HttpAdapter] Error executing WeApRous handler {handler.__name__}: {e}")
                err_msg = f"<h1>500 Internal Server Error</h1><p>Handler Error: {e}</p>"
                headers = f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(err_msg)}\r\nConnection: close\r\n\r\n"
                conn.sendall(headers.encode() + err_msg.encode())
                conn.close()
                return

        # ==========================================================
        # BƯỚC 2: LOGIC DỰ PHÒNG (Cho Backend 9000 - nếu không phải WeApRous)
        # ==========================================================
        print(f"[HttpAdapter] No WeApRous route found. Falling back to hardcoded logic for {req.method} {req.path}...")

        if req.method == "GET" and req.path == "/login":
            try:
                with open(os.path.join("www", "login.html"), "r", encoding="utf-8") as fh:
                    body = fh.read()
                headers = "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
                conn.sendall(headers.encode() + body.encode('utf-8'))
            except Exception as e:
                body = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())
            conn.close()
            return

        if req.method == "POST" and req.path == "/login":
            try:
                header_end = raw_req.find("\r\n\r\n")
                content_len = 0
                if header_end != -1:
                    headers_part = raw_req[:header_end]
                    for line in headers_part.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except Exception:
                                content_len = 0
                            break

                body = ""
                if header_end != -1 and content_len > 0:
                    start = header_end + 4
                    body_bytes = msg[start:start + content_len]
                    try:
                        body = body_bytes.decode("utf-8")
                    except Exception:
                        body = body_bytes.decode("latin-1", errors="ignore")
                else:
                    body = ""
            except Exception:
                body = ""

            print(f"[HttpAdapter] POST /login received: content_len={content_len} body_len={len(body)}")
            form = urllib.parse.parse_qs(body)
            username = form.get("username", [""])[0]
            password = form.get("password", [""])[0]

            if username and password:
                print(f"[HttpAdapter] POST /login parsed username={username}")
            else:
                print(f"[HttpAdapter] POST /login parsed empty credentials")
            users_file = os.path.join("www", "users.json")
            users = {}
            try:
                if os.path.exists(users_file):
                    with open(users_file, "r", encoding="utf-8") as f:
                        users = json.load(f)
                else:
                    print("[HttpAdapter] users.json not found, using default users.")
                    users = {
                        "admin": "password",
                        "client1": "123",
                        "client2": "123"
                    }
            except Exception as e:
                print(f"[HttpAdapter] Error reading users.json: {e}")
                users = {
                    "admin": "password",
                    "client1": "123",
                    "client2": "123"
                }
            if username in users and users[username] == password:
                try:
                    with open(os.path.join("www", "index.html"), "r", encoding="utf-8") as fh:
                        body = fh.read()
                    headers = ("HTTP/1.1 200 OK\r\n"
                               "Content-Type: text/html; charset=utf-8\r\n"
                               "Set-Cookie: auth=true; Path=/; HttpOnly; SameSite=Lax; Max-Age=3600\r\n"
                               "\r\n")
                    conn.sendall(headers.encode() + body.encode())
                except Exception as e:
                    body = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                    conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())
            else:
                try:
                    body = "<h1>401 Unauthorized</h1><p>Invalid credentials.</p>"
                    headers = ("HTTP/1.1 401 Unauthorized\r\n"
                               "Content-Type: text/html\r\n"
                               "Content-Length: {}\r\n"
                               "Connection: close\r\n"
                               "\r\n").format(len(body))
                    conn.sendall(headers.encode() + body.encode())
                except Exception:
                    conn.sendall(b"HTTP/1.1 401 Unauthorized\r\n\r\n<h1>401 Unauthorized</h1>")
            conn.close()
            return

        if req.method == "GET" and req.path == "/protected":
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<h1>Protected Resource</h1><p>You are logged in!</p>")
            conn.close()
            return

        if req.method == "GET" and req.path in ("/", "/index", "/index.html"):
            auth_val = ""
            try:
                # Debug: in ra cookies nhận được
                print(f"[HttpAdapter] GET / cookies: {req.cookies}")
                auth_val = req.cookies.get("auth", "")
                if isinstance(auth_val, str):
                    auth_val = auth_val.lower()
                print(f"[HttpAdapter] GET / auth_val: '{auth_val}'")
            except Exception as e:
                print(f"[HttpAdapter] Error reading cookies: {e}")
                auth_val = ""

            if auth_val == "true":
                try:
                    with open(os.path.join("www", "index.html"), "r", encoding="utf-8") as fh:
                        body = fh.read()
                    headers = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
                    conn.sendall(headers.encode() + body.encode())
                except Exception as e:
                    body = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                    conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())
                conn.close()
                return
            else:
                body = "<h1>401 Unauthorized</h1><p>Login required. <a href=\"/login\">Login</a></p>"
                headers = ("HTTP/1.1 401 Unauthorized\r\n"
                           "Content-Type: text/html; charset=utf-8\r\n"
                           "Content-Length: {}\r\n"
                           "Connection: close\r\n"
                           "\r\n").format(len(body))
                conn.sendall(headers.encode() + body.encode())
                conn.close()
                return
        if req.method == "GET" and req.path.startswith("/submit-info"):
            try:
                with open(os.path.join("www", "submit-info.html"), "r", encoding="utf-8") as fh:
                    body = fh.read()
                headers = "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
                conn.sendall(headers.encode() + body.encode('utf-8'))
            except Exception as e:
                body = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())
            conn.close()
            return
        
        if req.method == "POST" and req.path == "/submit-info":
            try:
                header_end = raw_req.find("\r\n\r\n")
                content_len = 0
                if header_end != -1:
                    headers_part = raw_req[:header_end]
                    for line in headers_part.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except Exception:
                                content_len = 0
                            break

                body = ""
                if header_end != -1 and content_len > 0:
                    start = header_end + 4
                    body_bytes = msg[start:start + content_len]
                    try:
                        body = body_bytes.decode("utf-8")
                    except Exception:
                        body = body_bytes.decode("latin-1", errors="ignore")
                else:
                    body = ""
            except Exception:
                body = ""

            print(f"[HttpAdapter] POST /submit-info received: content_len={content_len} body_len={len(body)}")

            # Parse dữ liệu form
            form = urllib.parse.parse_qs(body)
            username = form.get("username", [""])[0]
            password = form.get("password", [""])[0]

            if not username or not password:
                body = "<h1>400 Bad Request</h1><p>Missing username or password.</p>"
                headers = ("HTTP/1.1 400 Bad Request\r\n"
                        "Content-Type: text/html; charset=utf-8\r\n"
                        "Content-Length: {}\r\n"
                        "Connection: close\r\n\r\n").format(len(body))
                conn.sendall(headers.encode() + body.encode())
                conn.close()
                return

            print(f"[HttpAdapter] Register attempt via /submit-info: {username}")

            # Đọc danh sách người dùng từ file
            users_file = os.path.join("www", "users.json")
            users = {}
            try:
                if os.path.exists(users_file):
                    with open(users_file, "r", encoding="utf-8") as f:
                        users = json.load(f)
            except Exception as e:
                print(f"[HttpAdapter] Warning: cannot read users.json: {e}")
                users = {}

            # Kiểm tra trùng tên
            if username in users:
                body = f"<h1>409 Conflict</h1><p>Username '{username}' already exists.</p>"
                headers = ("HTTP/1.1 409 Conflict\r\n"
                        "Content-Type: text/html; charset=utf-8\r\n"
                        "Content-Length: {}\r\n"
                        "Connection: close\r\n\r\n").format(len(body))
                conn.sendall(headers.encode() + body.encode())
                conn.close()
                return

            # Lưu tài khoản mới
            users[username] = password
            try:
                with open(users_file, "w", encoding="utf-8") as f:
                    json.dump(users, f, ensure_ascii=False, indent=2)
            except Exception as e:
                body = f"<h1>500 Internal Server Error</h1><p>Cannot save user: {e}</p>"
                conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())
                conn.close()
                return

            # Gửi phản hồi thành công
            try:
                with open(os.path.join("www", "index.html"), "r", encoding="utf-8") as fh:
                    body = fh.read()
                    headers = ("HTTP/1.1 200 OK\r\n"
                               "Content-Type: text/html; charset=utf-8\r\n"
                               "Set-Cookie: auth=true; Path=/; HttpOnly; SameSite=Lax; Max-Age=3600\r\n"
                               "\r\n")
                    conn.sendall(headers.encode() + body.encode())
            except Exception as e:
                body = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())

            conn.close()
            return

        # --- Handle /add-list ---
        # server_routes.py
        # httpadapter.py

##############################################################################
        # --- /add-list --- (ghi vào peer_connections.json)
        if req.method == "POST" and req.path == "/add-list":
            try:
                import json, os
                header_end = raw_req.find("\r\n\r\n")
                body = ""
                if header_end != -1:
                    content_len = 0
                    headers_part = raw_req[:header_end]
                    for line in headers_part.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except Exception:
                                content_len = 0
                            break
                    if content_len > 0:
                        start = header_end + 4
                        body_bytes = msg[start:start + content_len]
                        body = body_bytes.decode("utf-8", errors="ignore")

                # --- parse JSON ---
                data = json.loads(body)
                user = data.get("user")
                host = data.get("host", "127.0.0.1")
                port = data.get("port")
                item = data.get("item", "ONLINE")

                if not user:
                    raise ValueError("Missing 'user' field")

                os.makedirs("db", exist_ok=True)
                if os.path.exists(PEER_CONNECTION_FILE):
                    try:
                        with open(PEER_CONNECTION_FILE, "r", encoding="utf-8") as f:
                            connections = json.load(f)
                    except Exception:
                        connections = {}
                else:
                    connections = {}

                # --- cập nhật thông tin peer ---
                if user not in connections:
                    connections[user] = []

                # chỉ lưu chính bản thân peer (host, port, trạng thái)
                peer_entry = {"peer": user, "ip": host, "port": port, "status": item}
                # ghi đè bản ghi cũ nếu đã tồn tại
                connections[user] = [peer_entry]

                with open(PEER_CONNECTION_FILE, "w", encoding="utf-8") as f:
                    json.dump(connections, f, indent=4, ensure_ascii=False)

                # --- phản hồi ---
                resp = {"message": f"Peer '{user}' added to connection list", "peer": peer_entry}
                body_resp = json.dumps(resp)
                headers = (
                    f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(body_resp)}\r\n"
                    f"Connection: close\r\n\r\n"
                )
                conn.sendall(headers.encode() + body_resp.encode())

            except Exception as e:
                err = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                conn.sendall(
                    f"HTTP/1.1 500 Internal Server Error\r\n"
                    f"Content-Type: text/html; charset=utf-8\r\n"
                    f"Content-Length: {len(err)}\r\n"
                    f"Connection: close\r\n\r\n".encode() + err.encode()
                )
            finally:
                conn.close()


        # #################################################
        # --- /1sx1 ---
        if req.method == "GET" and req.path == "/get-list":
            try:
                if not os.path.exists(PEER_CONNECTION_FILE):
                    resp = {"count": 0, "list": []}
                else:
                    with open(PEER_CONNECTION_FILE, "r", encoding="utf-8") as f:
                        connections = json.load(f)

                    # gộp toàn bộ các peer thành danh sách
                    all_peers = []
                    for peer_name, peer_entries in connections.items():
                        for entry in peer_entries:
                            all_peers.append(entry)

                    resp = {"count": len(all_peers), "list": all_peers}

                body_resp = json.dumps(resp)
                headers = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(body_resp)}\r\nConnection: close\r\n\r\n"
                conn.sendall(headers.encode() + body_resp.encode())
            except Exception as e:
                body_bytes = f"<h1>500 Internal Server Error</h1><p>{e}</p>".encode()
                headers = f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(body_bytes)}\r\nConnection: close\r\n\r\n"
                conn.sendall(headers.encode() + body_bytes)
            finally:
                conn.close()


##########################################################
# --- /connect-peer (đọc/ghi peer_connections.json) ---
        if req.method == "POST" and req.path == "/connect-peer":
            try:
                import json, os

                # --- Đọc body từ request ---
                raw_req = msg.decode(errors="ignore")
                header_end = raw_req.find("\r\n\r\n")
                body = ""
                if header_end != -1:
                    headers_part = raw_req[:header_end]
                    content_len = 0
                    for line in headers_part.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except Exception:
                                content_len = 0
                            break
                    if content_len > 0:
                        start = header_end + 4
                        body_bytes = msg[start:start + content_len]
                        body = body_bytes.decode("utf-8", errors="ignore")

                if not body.strip():
                    raise ValueError("Empty or missing JSON body in /connect-peer request")

                # --- Parse JSON ---
                data = json.loads(body)
                from_user = data.get("from_user")
                to_peer = data.get("to_peer")
                if not from_user or not to_peer:
                    raise ValueError("Missing 'from_user' or 'to_peer' in JSON body")

                # --- Đọc file peer_connections.json ---
                if not os.path.exists(PEER_CONNECTION_FILE):
                    raise FileNotFoundError(f"{PEER_CONNECTION_FILE} not found")

                with open(PEER_CONNECTION_FILE, "r", encoding="utf-8") as f:
                    try:
                        connections = json.load(f)
                    except json.JSONDecodeError:
                        connections = {}

                # --- Lấy thông tin của 2 peer từ file ---
                from_info_list = connections.get(from_user, [])
                to_info_list = connections.get(to_peer, [])
                if not from_info_list or not to_info_list:
                    raise ValueError(f"Peer '{from_user}' or '{to_peer}' not found in {PEER_CONNECTION_FILE}")

                from_info = from_info_list[0]
                to_info = to_info_list[0]

                # --- Tạo dữ liệu 2 chiều ---
                from_peer_data = {
                    "peer": to_peer,
                    "ip": to_info.get("ip", "127.0.0.1"),
                    "port": to_info.get("port")
                }
                to_peer_data = {
                    "peer": from_user,
                    "ip": from_info.get("ip", "127.0.0.1"),
                    "port": from_info.get("port")
                }

                # --- Gắn kết nối 2 chiều ---
                if from_user not in connections:
                    connections[from_user] = []
                if not any(p["peer"] == to_peer for p in connections[from_user]):
                    connections[from_user].append(from_peer_data)

                if to_peer not in connections:
                    connections[to_peer] = []
                if not any(p["peer"] == from_user for p in connections[to_peer]):
                    connections[to_peer].append(to_peer_data)

                # --- Ghi lại file ---
                os.makedirs(os.path.dirname(PEER_CONNECTION_FILE), exist_ok=True)
                with open(PEER_CONNECTION_FILE, "w", encoding="utf-8") as f:
                    json.dump(connections, f, ensure_ascii=False, indent=4)

                # --- Phản hồi ---
                resp = {
                    "message": f"Successfully connected {from_user} ↔ {to_peer}",
                    "from_user": from_user,
                    "to_peer": to_peer,
                    "connected_to": from_peer_data
                }
                body_resp = json.dumps(resp, ensure_ascii=False)
                headers = (
                    f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(body_resp)}\r\n"
                    f"Connection: close\r\n\r\n"
                )
                conn.sendall(headers.encode() + body_resp.encode())

                print(f"[Tracker] ✅ Connected {from_user} ↔ {to_peer}")

            except Exception as e:
                err_msg = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                headers = (
                    f"HTTP/1.1 500 Internal Server Error\r\n"
                    f"Content-Type: text/html\r\n"
                    f"Content-Length: {len(err_msg)}\r\n"
                    f"Connection: close\r\n\r\n"
                )
                conn.sendall(headers.encode() + err_msg.encode())
                print(f"[Tracker] ❌ error /connect-peer: {e}")

            finally:
                conn.close()

# --------------------------------------

        import socket

# --------------------------------------
# /broadcast-peer (sửa)
# --------------------------------------
        if req.method == "POST" and req.path == "/broadcast-peer":
            try:
                # --- Đọc body JSON ---
                header_end = raw_req.find("\r\n\r\n")
                content_len = 0
                if header_end != -1:
                    headers_part = raw_req[:header_end]
                    for line in headers_part.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except:
                                content_len = 0
                            break

                body = ""
                if header_end != -1 and content_len > 0:
                    start = header_end + 4
                    body_bytes = msg[start:start + content_len]
                    body = body_bytes.decode("utf-8", errors="ignore")

                # --- Parse JSON ---
                import json
                data = json.loads(body)
                sender = data.get("from_user") or data.get("from")
                message = data.get("message")
                if not sender or not message:
                    raise ValueError("Missing 'from_user' or 'message'")

                # --- Đọc file kết nối thật ---
                if not os.path.exists(PEER_CONNECTION_FILE):
                    raise FileNotFoundError(f"File {PEER_CONNECTION_FILE} not found")

                with open(PEER_CONNECTION_FILE, "r", encoding="utf-8") as f:
                    connections = json.load(f)

                if sender not in connections:
                    raise ValueError(f"Sender '{sender}' not found in connections list")

                peers = connections[sender]
                success = 0

                print(f"[Broadcast] {sender} gửi '{message}' tới {len(peers)} peers: {[p['peer'] for p in peers]}")

                # # --- Gửi message tới từng peer ---
                # for peer in peers:
                #     ip = peer.get("ip")
                #     port = peer.get("port")
                #     peer_name = peer.get("peer")
                #     try:
                #         s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                #         s.connect((ip, int(port)))
                #         s.sendall(f"[Broadcast from {sender}] {message}".encode("utf-8"))
                #         s.close()
                #         success += 1
                #     except Exception as e:
                #         print(f"[Broadcast] error {peer_name} ({e})")
                # --- Phản hồi kết quả ---
                body = f"<h1>Broadcast sent</h1><p>Message delivered to {success} peers.</p>"
                headers = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: text/html; charset=utf-8\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                )
                conn.sendall(headers.encode() + body.encode())

                

            except Exception as e:
                err = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                conn.sendall(
                    f"HTTP/1.1 500 Internal Server Error\r\n"
                    f"Content-Type: text/html; charset=utf-8\r\n"
                    f"Content-Length: {len(err)}\r\n"
                    f"Connection: close\r\n\r\n".encode() + err.encode()
                )
                print(f"[Broadcast] error /broadcast-peer: {e}")
            finally:
                conn.close()


# --------------------------------------
# /send-peer (sửa)
# --------------------------------------
        if req.method == "POST" and req.path == "/send-peer":
            try:
                # --- đọc body JSON ---
                header_end = raw_req.find("\r\n\r\n")
                content_len = 0
                if header_end != -1:
                    headers_part = raw_req[:header_end]
                    for line in headers_part.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except:
                                content_len = 0
                            break

                body = ""
                if header_end != -1 and content_len > 0:
                    start = header_end + 4
                    body_bytes = msg[start:start + content_len]
                    body = body_bytes.decode("utf-8", errors="ignore")

                data = json.loads(body)
                sender = data.get("from_user") or data.get("from")
                target = data.get("to")
                message = data.get("message")

                if not sender or not target or not message:
                    raise ValueError("Missing required fields: from_user, to, message")

                # --- Đọc file peer_connections.json ---
                if not os.path.exists(PEER_CONNECTION_FILE):
                    raise FileNotFoundError(f"{PEER_CONNECTION_FILE} not found")

                with open(PEER_CONNECTION_FILE, "r", encoding="utf-8") as f:
                    connections = json.load(f)

                # --- Tìm IP/Port của target ---
                target_info = None
                if sender in connections:
                    for peer in connections[sender]:
                        if peer.get("peer") == target:
                            target_info = peer
                            break

                if not target_info:
                    raise ValueError(f"Peer '{target}' not found in {PEER_CONNECTION_FILE}")

                ip = target_info.get("ip", "127.0.0.1")
                port = int(target_info.get("port", 0))

                # --- Gửi message ---
                # s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # s.connect((ip, port))
                # s.sendall(f"[Private] {sender}: {message}".encode("utf-8"))
                # s.close()

                body = f"<h1>Message sent</h1><p>{sender} → {target}</p>"
                headers = ("HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/html; charset=utf-8\r\n"
                        f"Content-Length: {len(body)}\r\n\r\n")
                conn.sendall(headers.encode() + body.encode())

                

            except Exception as e:
                err = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                conn.sendall(
                    f"HTTP/1.1 500 Internal Server Error\r\n"
                    f"Content-Type: text/html; charset=utf-8\r\n"
                    f"Content-Length: {len(err)}\r\n\r\n".encode() + err.encode('utf-8')
                )
               

            finally:
                conn.close()