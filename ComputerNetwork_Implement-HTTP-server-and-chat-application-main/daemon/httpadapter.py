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

from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

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
        """
        Initialize a new HttpAdapter instance.

        :param ip (str): IP address of the client.
        :param port (int): Port number of the client.
        :param conn (socket): Active socket connection.
        :param connaddr (tuple): Address of the connected client.
        :param routes (dict): Mapping of route paths to handler functions.
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes
        #: Request
        self.request = Request()
        #: Response
        self.response = Response()

    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """

        # Local import to access backend.sessions
        from . import backend
        import socket
        import os

        # Connection/context
        self.conn = conn
        self.connaddr = addr
        req = self.request
        resp = self.response

        # Read raw request (non-blocking-ish with timeout)
        import time

        msg = b""
        conn.settimeout(0.5)
        deadline = time.time() + 2.0  # total wait time for headers+body
        raw_req = ""

        while True:
            try:
                chunk = conn.recv(4096)
                if not chunk:
                    # client closed or nothing more right now
                    break
                msg += chunk
            except socket.timeout:
                # allow loop to continue until deadline
                if time.time() > deadline:
                    break
                continue

            # try decode current buffer for header parsing
            try:
                raw_req = msg.decode(errors="ignore")
            except Exception:
                raw_req = ""

            header_end = raw_req.find("\r\n\r\n")
            if header_end == -1:
                # haven't received headers end yet -> continue reading until deadline
                if time.time() > deadline:
                    break
                else:
                    continue

            # headers found -> parse Content-Length and ensure full body read
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
            # if we already have full body, stop reading
            if content_len == 0 or body_bytes_len >= content_len:
                break

            # otherwise continue reading until we have full body or deadline exceeded
            if time.time() > deadline:
                break
            # extend deadline a bit to allow remaining body to arrive
            deadline = max(deadline, time.time() + 2.0)
            continue

        # debug: show bytes received & preview (helps track missing POST body)
        try:
            raw_req = msg.decode(errors="ignore")
        except Exception:
            raw_req = ""
        # Minimal logging: only show bytes received when it's a POST /login (important)
        try:
            first_line = raw_req.splitlines()[0] if raw_req else ""
        except Exception:
            first_line = ""
        if first_line.startswith("POST /login"):
            print(f"[HttpAdapter] recv bytes={len(msg)} header_end={raw_req.find('\\r\\n\\r\\n')}")
        # otherwise keep quiet (other requests are handled silently)

        # now we should have headers + (possibly) full body in msg/raw_req
        # Prepare request object: pass decoded raw string (raw_req) to match Request.prepare expectations
        # Request.prepare expects str
        req.prepare(raw_req, routes)

        # --- Handle GET /login: show login form ---
        if req.method == "GET" and req.path == "/login":
            try:
                with open(os.path.join("www", "login.html"), "r", encoding="utf-8") as fh:
                    body = fh.read()
                headers = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
                conn.sendall(headers.encode() + body.encode())
            except Exception as e:
                body = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())
            conn.close()
            return

        # --- Handle POST /login: check credentials ---
        if req.method == "POST" and req.path == "/login":
            import urllib.parse

            # Safely extract Content-Length and body bytes from raw_req/msg
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
                # extract body bytes directly from msg
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

            # Minimal logging + parse form
            print(f"[HttpAdapter] POST /login received: content_len={content_len} body_len={len(body)}")
            form = urllib.parse.parse_qs(body)
            username = form.get("username", [""])[0]
            password = form.get("password", [""])[0]

            # Log result only (do not print password)
            if username and password:
                print(f"[HttpAdapter] POST /login parsed username={username}")
            else:
                print(f"[HttpAdapter] POST /login parsed empty credentials")

            # Simple credential check (for demonstration)
            if username == "admin" and password == "password":
                # Successful login: respond with index page and set auth cookie
                try:
                    with open(os.path.join("www", "index.html"), "r", encoding="utf-8") as fh:
                        body = fh.read()
                    headers = ("HTTP/1.1 200 OK\r\n"
                               "Content-Type: text/html\r\n"
                               "Set-Cookie: auth=true; Path=/; HttpOnly\r\n"
                               "\r\n")
                    conn.sendall(headers.encode() + body.encode())
                except Exception as e:
                    body = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
                    conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n" + body.encode())
            else:
                # Failed login: respond with 401 Unauthorized
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

        # --- Handle GET /protected: show protected resource ---
        if req.method == "GET" and req.path == "/protected":
            # For simplicity, assume any authenticated user can access /protected
            # In real app, check session or auth token here
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<h1>Protected Resource</h1><p>You are logged in!</p>")
            conn.close()
            return

        # --- Serve index for / or /index as convenience ---
        if req.method == "GET" and req.path in ("/", "/index", "/index.html"):
            # Check cookie-based auth
            auth_val = ""
            try:
                auth_val = req.cookies.get("auth", "")
                # normalize boolean-like values
                if isinstance(auth_val, str):
                    auth_val = auth_val.lower()
            except Exception:
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
                # Not authenticated -> 401
                body = "<h1>401 Unauthorized</h1><p>Login required. <a href=\"/login\">Login</a></p>"
                headers = ("HTTP/1.1 401 Unauthorized\r\n"
                           "Content-Type: text/html\r\n"
                           "Content-Length: {}\r\n"
                           "Connection: close\r\n"
                           "\r\n").format(len(body))
                conn.sendall(headers.encode() + body.encode())
                conn.close()
                return

        # --- 404 Not Found ---
        conn.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n<h1>404 Not Found</h1>")
        conn.close()