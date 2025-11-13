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
daemon.request
~~~~~~~~~~~~~~~~~

This module provides a Request object to manage and persist 
request settings (cookies, auth, proxies).
"""
from .dictionary import CaseInsensitiveDict
from .session_store import get_user_from_session  # added import

DEBUG = True  # set True only when debugging

class Request():
    """The fully mutable "class" `Request <Request>` object,
    containing the exact bytes that will be sent to the server.

    Instances are generated from a "class" `Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    Usage::

      >>> import deamon.request
      >>> req = request.Request()
      ## Incoming message obtain aka. incoming_msg
      >>> r = req.prepare(incoming_msg)
      >>> r
      <Request>
    """
    __attrs__ = [
        "method",
        "url",
        "headers",
        "body",
        "reason",
        "cookies",
        "body",
        "routes",
        "hook",
        "auth",    # added
        "user",    # added
    ]

    def __init__(self):
        #: HTTP verb to send to the server.
        self.method = None
        #: HTTP URL to send the request to.
        self.url = None
        #: dictionary of HTTP headers.
        self.headers = None
        #: HTTP path
        self.path = None        
        # The cookies set used to create Cookie header
        self.cookies = None
        #: request body to send to the server.
        self.body = None
        #: Routes
        self.routes = {}
        #: Hook point for routed mapped-path
        self.hook = None
        # Authentication/user info (set by prepare if session cookie present)
        self.user = None
        self.auth = False

    def extract_request_line(self, request):
        try:
            lines = request.splitlines()
            if not lines:
                print("[Request] Empty request received.")
                return "GET", "/index.html", "HTTP/1.1"

            first_line = lines[0].strip()
            if DEBUG:
                print(f"[Request] Raw first line: {first_line}")
            parts = first_line.split()

            if len(parts) == 3:
                method, path, version = parts
            elif len(parts) == 2:
                method, path = parts
                version = "HTTP/1.1"
            else:
                print("[Request] Invalid request line format.")
                return "GET", "/index.html", "HTTP/1.1"

            if path == '/':
                path = '/index.html'

            return method, path, version

        except Exception as e:
            print(f"[Request] Error extracting request line: {e}")
            # Trả giá trị mặc định an toàn để backend không crash
            return "GET", "/index.html", "HTTP/1.1"
    
    def prepare_headers(self, request):
        """Prepares the given HTTP headers."""
        lines = request.split('\r\n')
        headers = {}
        for line in lines[1:]:
            if ': ' in line:
                key, val = line.split(': ', 1)
                headers[key.lower()] = val
        return headers

    def prepare(self, request, routes=None):
        """Prepares the entire request with the given parameters."""

        # Prepare the request line from the request header
        self.method, self.path, self.version = self.extract_request_line(request)
        if DEBUG:
            print(f"[Request] {self.method} path {self.path} version {self.version}")

        #
        # @bksysnet Preapring the webapp hook with WeApRous instance
        # The default behaviour with HTTP server is empty routed
        #
        # TODO manage the webapp hook in this mounting point
        #
        
        if not routes == {}:
            self.routes = routes
            self.hook = routes.get((self.method, self.path))
            #
            # self.hook manipulation goes here
            # ...
            #

        self.headers = self.prepare_headers(request)
        cookies = self.headers.get('cookie', '')
        #
        #  TODO: implement the cookie function here
        #        by parsing the header            #

        if DEBUG:
            print(f"[Request] Raw cookie header: '{cookies}'")
        
        if cookies:
            cookie_dict = {}
            # Split by ';' or '; ' (handle both formats)
            for pair in cookies.split(';'):
                pair = pair.strip()
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    cookie_dict[k.strip()] = v.strip()
            if DEBUG:
                print(f"[Request] Parsed cookies: {cookie_dict}")
            self.cookies = cookie_dict
        else:
            if DEBUG:
                print("[Request] No cookies found in request")
            self.cookies = {}

        # --- session integration: check 'sessionid' cookie and resolve user ---
        try:
            sessionid = self.cookies.get('sessionid')
            if sessionid:
                user = get_user_from_session(sessionid)
                if user:
                    self.user = user
                    self.auth = True
                else:
                    self.user = None
                    self.auth = False
            else:
                self.user = None
                self.auth = False
        except Exception:
            # on any error, default to unauthenticated
            self.user = None
            self.auth = False
        # end session integration

        return

    def prepare_body(self, body, files=None, json=None):
        # set body and content-length properly
        self.body = body
        self.prepare_content_length(self.body)
        #
        # TODO prepare the request authentication
        #
        return

    def prepare_content_length(self, body):
        # ensure headers exists
        if self.headers is None:
            self.headers = {}
        length = 0
        if body is None:
            length = 0
        else:
            # bytes/bytearray
            if isinstance(body, (bytes, bytearray)):
                length = len(body)
            # str -> encode to utf-8 to compute bytes length
            elif isinstance(body, str):
                length = len(body.encode('utf-8'))
            else:
                # fallback: try len()
                try:
                    length = len(body)
                except Exception:
                    length = 0
        self.headers["Content-Length"] = str(length)
        return

    def prepare_cookies(self, cookies):
        if self.headers is None:
            self.headers = {}
        # accept dict or cookie string
        if isinstance(cookies, dict):
            cookie_str = '; '.join(f"{k}={v}" for k, v in cookies.items())
        else:
            cookie_str = str(cookies)
        self.headers["Cookie"] = cookie_str
        return
