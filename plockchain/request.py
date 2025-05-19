import json
import xml.etree.ElementTree as ET
from pathlib import Path
import jq


class Header:
    """
    Class for store header data
    """

    def __init__(self, raw_headers):
        self.headers_dict = {}
        for header in raw_headers.split(sep=b"\r\n")[1:]:
            key, value = header.split(sep=b": ", maxsplit=1)
            self.headers_dict[key.decode()] = value.decode()

        self.headers_list = []
        self.__update_headers_list()

    def __update_headers_list(self):
        self.headers_list = [f"{k}: {v}" for k, v in self.headers_dict.items()]

    def add(self, key: str, value: str):
        self.headers_dict[key] = value
        self.__update_headers_list()

    def remove(self, key: str):
        del self.headers_dict[key]
        self.__update_headers_list()

    def get(self, key: str):
        if key in self.headers_dict:
            return self.headers_dict[key]
        else:
            try:
                return self.headers_dict[key.lower()]
            except KeyError:
                return None

    @property
    def raw(self):
        raw_headers = b""
        for key, value in self.headers_dict.items():
            raw_headers += f"{key}: {value}\r\n".encode()
        return raw_headers.strip()


class Body:
    """
    Class for store body data
    """

    X_WWW_FORM_URLENCODED = "application/x-www-form-urlencoded"
    JSON = "application/json"
    XML = "application/xml"
    OCTET_STREAM = "application/octet-stream"

    def __init__(self, raw_body: bytes, content_type: str | None = None):
        # Try to decode
        try:
            self.body = raw_body.decode().strip()
        except UnicodeDecodeError:
            self.body = raw_body

        self.content_type = content_type

        if self.content_type is None:
            self.content_type = self.__detect_content_type()

    def get(self, key):
        if self.content_type == self.X_WWW_FORM_URLENCODED:
            return
        elif self.content_type == self.JSON:
            try:
                json_body = json.loads(self.body)
            except json.JSONDecodeError:
                return None
            return jq.compile(key).input(json_body).all()
        elif self.content_type == self.XML:
            return
        else:
            return None

    def __detect_content_type(self):
        """Detect content type"""
        if isinstance(self.body, str):
            # JSON detect
            try:
                json.loads(self.body)
                return self.JSON
            except json.JSONDecodeError:
                pass

            # XML detect
            try:
                ET.fromstring(self.body)
                return self.XML
            except ET.ParseError:
                pass

            # url form encoded
            return self.X_WWW_FORM_URLENCODED
        else:
            # Multipart form
            pass

        return self.OCTET_STREAM

    @property
    def raw(self):
        if isinstance(self.body, str):
            return self.body.encode()
        return self.body


class Request:
    """
    Class for store request data
    """

    def __init__(
        self,
        connection: tuple,
        req: bytes,
        use_tls: bool = False,
        timeout: float = 5.0,
        import_config: dict | None = None,
        export_config: dict | None = None,
    ):
        self.importer_config = import_config
        self.exporter_config = export_config
        self.use_tls = use_tls
        self.timeout = timeout

        self.host, self.port = connection

        self.raw_headers, self.raw_body = req.split(sep=b"\r\n\r\n", maxsplit=1)
        self.header = Header(self.raw_headers)

        # Load host on auto mode
        if self.host is None or self.host == "" or self.host == "auto":
            self.host = self.header.get("Host")
        if self.port is None or self.port == "auto":
            if self.use_tls:
                self.port = 443
            else:
                self.port = 80

        first_line = self.raw_headers.split(sep=b"\r\n")[0]
        self.method, self.path, self.version = first_line.split(sep=b" ", maxsplit=2)

        if self.method.lower() != b"get":
            self.body = Body(self.raw_body, self.header.get("Content-Type"))

    def add_header(self, key: str, value: str):
        self.header.add(key, value)

    def remove_header(self, key: str):
        self.header.remove(key)

    def get_header(self, key: str):
        return self.header.get(key)

    @property
    def raw(self):
        return (
            self.method
            + b" "
            + self.path
            + b" "
            + self.version
            + b"\r\n"
            + self.header.raw
            + b"\r\n\r\n"
            + self.raw_body
        )

    def copy(self):
        return Request(
            (self.host, self.port),
            self.raw,
            self.use_tls,
            self.timeout,
            self.importer_config,
            self.exporter_config,
        )

    def run(self, global_vars: dict, proxy_config: dict | None):
        """Run request"""
        request_to_run = self.copy()
        request_to_run.importer(global_vars)
        # Start req handler

        http_res = send_http_request(
            self.host,
            self.port,
            request_to_run.raw,
            self.timeout,
            self.use_tls,
            proxy_config,
        )
        request_to_run.response = Response(http_res)
        # End req handler
        request_to_run.exporter(global_vars)

    def exporter(self, global_vars: dict):
        if self.exporter_config is None:
            return

        for key, value in self.exporter_config.items():
            if key not in ["request", "response"]:
                continue

            for pos, val in value.items():
                if pos not in ["body", "header"]:
                    continue

                var_obj = val.get("var")
                if var_obj is None:
                    continue

                if pos == "body":
                    if getattr(self, "response", None) is None:
                        raise ValueError("The request has not been run yet")
                    tmp = self.response.body.get(var_obj.get("key"))
                    if len(tmp) == 0:
                        continue
                    if len(tmp) != 1:
                        raise ValueError("The key must be unique")
                    tmp = tmp[0]
                    global_vars[var_obj.get("name")] = tmp

    def importer(self, global_vars: dict):
        if self.importer_config is None:
            return

        sources = set(self.importer_config.keys())
        if "vars" in sources:
            vars_config = self.importer_config.get("vars")
            for var_obj in vars_config:
                var = var_obj.get("var")
                if var is None:
                    continue

                var_name = var.get("name", "")
                var_value = global_vars.get(var_name, None)
                if var_value is None:
                    raise ValueError(f"Variable {var_name} not found")

                dest = var.get("dest", None)
                if dest is None:
                    continue

                if dest.get("pos", None) == "header":
                    key = dest.get("key", None)
                    if key is None:
                        continue

                    prefix = dest.get("prefix", "")
                    self.header.add(key, prefix + var_value)

    @staticmethod
    def parse_request(base_dir: Path, req_conf: dict) -> object:
        """Parse request from file"""
        filename = base_dir / req_conf.get("name")
        if filename is None:
            raise ValueError("Filename is None")

        with open(file=filename, mode="rb") as req:
            data = req.read()

        export_config = req_conf.get("export", None)
        import_config = req_conf.get("import", None)

        use_tls = req_conf.get("use_tls", True)
        timeout = req_conf.get("timeout", 5.0)

        host = req_conf.get("host")
        port = req_conf.get("port")

        if host is None or port is None:
            raise ValueError("Host or port is None")

        req = Request(
            (host, port), data, use_tls, timeout, import_config, export_config
        )
        return req


class Response:
    """
    Class for store response data
    """

    def __init__(self, response: bytes):
        self.raw_headers, self.raw_body = response.split(sep=b"\r\n\r\n", maxsplit=1)
        self.header = Header(self.raw_headers)
        self.body = Body(self.raw_body)


import socket
import ssl
from typing import Optional, Dict


def send_http_request(
    host: str,
    port: int,
    raw_req: bytes,
    timeout: float = 5.0,
    use_tls: bool = False,
    proxy: Optional[Dict[str, any]] = None,
) -> bytes:
    """
    Sends an HTTP request via optional HTTP proxy.

    If proxy is provided, will use HTTP CONNECT for HTTPS or full-URL GET for HTTP.
    """
    # 1. Khởi tạo socket và timeout
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    # 2. Kết nối tới proxy hoặc tới host đích trực tiếp
    if proxy:
        proxy_host = proxy["host"]
        proxy_port = proxy["port"]
        sock.connect((proxy_host, proxy_port))

        # 3. Nếu HTTPS: gửi CONNECT
        if use_tls:
            connect_req = (
                f"CONNECT {host}:{port} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                f"Proxy-Connection: keep-alive\r\n\r\n"
            ).encode()
            sock.sendall(connect_req)

            # Chờ proxy trả về 200 Connection Established
            resp = b""
            while b"\r\n\r\n" not in resp:
                resp += sock.recv(4096)
            if b"200 Connection" not in resp.split(b"\r\n")[0]:
                raise RuntimeError(
                    "Proxy CONNECT failed: " + resp.split(b"\r\n")[0].decode()
                )

            # 4. Bọc SSL lên socket đã “tunel”
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock, server_hostname=host)

        # 5. Nếu HTTP không mã hoá: sửa dòng request để chứa URL đầy đủ
        else:
            # Giả định header bắt đầu bằng b"GET /path HTTP/1.1\r\n"
            # Thay thành b"GET http://host:port/path HTTP/1.1\r\n"
            header_str = raw_header.decode()
            first_line, rest = header_str.split("\r\n", 1)
            method, path, version = first_line.split(" ", 2)
            full_url = f"{method} http://{host}:{port}{path} {version}\r\n"
            raw_header = full_url.encode() + rest.encode()

    else:
        # Kết nối trực tiếp tới server đích
        sock.connect((host, port))
        if use_tls:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock, server_hostname=host)

    # 6. Gửi header + body
    sock.sendall(raw_req)

    # 7. Nhận response
    response = b""
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
    except socket.timeout:
        print(f"Socket timed out after {timeout} seconds")

    sock.close()
    return response
