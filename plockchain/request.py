import json
import xml.etree.ElementTree as ET
import jq
import logging


logger = logging.getLogger(__name__)


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
        if key in self.headers_dict:
            self.headers_dict[key] = value
        else:
            try:
                self.headers_dict[key.lower()] = value
            except KeyError:
                return None
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

        if raw_body.strip() != b"":
            self.content_type = content_type
            if self.content_type is None:
                self.content_type = self.__detect_content_type()
            else:
                self.content_type = self.content_type.split(sep=";")[0]
                if self.content_type == self.OCTET_STREAM:
                    # Redetect
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

    def add(self, key, value):
        if self.content_type == self.X_WWW_FORM_URLENCODED:
            return
        elif self.content_type == self.JSON:
            try:
                json_body = json.loads(self.body)
            except json.JSONDecodeError:
                return None
            updated_body = jq.compile(f'{key}|="{value}"').input(json_body).first()
            self.body = json.dumps(updated_body, separators=(",", ":"))
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
        timeout: float = 30.0,
        import_config: dict | None = None,
        export_config: dict | None = None,
        events: list | None = None,
        auto_update_content_length: bool = True,
    ):
        self.importer_config = import_config
        self.exporter_config = export_config
        self.use_tls = use_tls
        self.timeout = timeout
        self.auto_update_content_length = auto_update_content_length

        self.host, self.port = connection

        self.raw_headers, self.raw_body = req.split(sep=b"\r\n\r\n", maxsplit=1)
        self.header = Header(self.raw_headers)

        # Load host on auto mode
        if self.host is None or self.host == "" or self.host == "auto":
            self.host = self.header.get("Host").split(sep=":")[0]
        # Load port on auto mode
        if self.port is None or self.port == "auto":
            if len(self.header.get("Host").split(sep=":")) == 2:
                self.port = self.header.get("Host").split(sep=":")[1]
            else:
                self.port = 443 if self.use_tls else 80

        first_line = self.raw_headers.split(sep=b"\r\n")[0]
        self.method, self.path, self.version = first_line.split(sep=b" ", maxsplit=2)

        self.body = Body(self.raw_body, self.header.get("Content-Type"))

        self.events = events

    def add_header(self, key: str, value: str):
        self.header.add(key, value)

    def remove_header(self, key: str):
        self.header.remove(key)

    def get_header(self, key: str):
        return self.header.get(key)

    def __update_content_length(self):
        if self.body is None:
            return
        self.header.add("Content-Length", str(len(self.body.raw)))

    @property
    def raw(self):
        if self.auto_update_content_length:
            self.__update_content_length()
        return (
            self.method
            + b" "
            + self.path
            + b" "
            + self.version
            + b"\r\n"
            + self.header.raw
            + b"\r\n\r\n"
            + self.body.raw
        )

    def copy(self):
        return Request(
            (self.host, self.port),
            self.raw,
            self.use_tls,
            self.timeout,
            self.importer_config,
            self.exporter_config,
            self.events,
            self.auto_update_content_length,
        )

    def run(self, global_vars, proxy_config: dict | None, support_chains: dict | None):
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

        resend = False
        for event in request_to_run.events:
            conditions = event.get("conditions")
            triggers = event.get("triggers")

            for cond, exp in conditions.items():
                if cond not in ["status", "header", "body"]:
                    raise ValueError("Condition must be in [status, header, body]")

                if cond == "status":
                    if request_to_run.response.status_code in [
                        i.strip() for i in str(exp).encode().split(b",")
                    ]:
                        chains = triggers.get("chains", None)
                        if chains is not None:
                            if not isinstance(chains, list):
                                raise ValueError("Chain must be a list in triggers")

                            for chain in chains:
                                chain_to_be_run = support_chains.get(chain, None)
                                if chain_to_be_run is None:
                                    raise ValueError(f"Chain {chain} not found")
                                # print(chain_to_be_run)
                                chain_to_be_run.run(
                                    custom_support_chains=support_chains
                                )
                            resend = True
                            # Skip the other checking
                            continue

                        # Checking if trigger skip event
                        skip_the_chain = triggers.get("skip", False)
                        if skip_the_chain:
                            logger.error(
                                f"Skip the chain in request {request_to_run.path} by event status code in {exp}"
                            )
                            global_vars["skip_the_chain"] = True
                            return

                        # Checking delay event
                        delay_time = triggers.get("delay", 0)
                        if delay_time > 0:
                            global_vars["delay_time"] = delay_time

                    continue

                if cond == "body":
                    if str(exp).encode() in request_to_run.response.body.raw:
                        chains = triggers.get("chains", None)
                        if chains is None or not isinstance(chains, list):
                            raise ValueError("Chain must be a list in triggers")

                        for chain in chains:
                            if chain.endswith(".yaml"):
                                pass
                                # TODO: Check and testing for load chain from other file.
                                from .parser import Parser
                                from .chain import RequestChain

                                new_outside_chain: RequestChain = Parser.parse_config(
                                    chain
                                )
                                new_outside_chain.run(
                                    custom_support_chains=support_chains,
                                    custom_vars=global_vars,
                                )
                            chain_to_be_run = support_chains.get(chain, None)
                            if chain_to_be_run is None:
                                raise ValueError(f"Chain {chain} not found")
                            # print(chain_to_be_run)
                            chain_to_be_run.run(
                                custom_support_chains=support_chains,
                                custom_vars=global_vars,
                            )
                        resend = True
                    continue

                raise NotImplementedError(f"{cond} Not implemented yet")

        if not resend:
            request_to_run.exporter(global_vars)
            return

        # Resend the request
        request_to_run.importer(global_vars)
        http_res = send_http_request(
            self.host,
            self.port,
            request_to_run.raw,
            self.timeout,
            self.use_tls,
            proxy_config,
        )
        request_to_run.response = Response(http_res)

        request_to_run.exporter(global_vars)
        return request_to_run

    def exporter(self, global_vars):
        if self.exporter_config is None:
            return

        for key, value in self.exporter_config.items():
            if key not in ["request", "response"]:
                continue

            if key == "response" and getattr(self, "response", None) is None:
                raise ValueError("The request has not been run yet")

            for pos, val in value.items():
                if pos not in ["body", "header"]:
                    continue

                var_objs = val.get("vars")
                if var_objs is None:
                    continue

                for var_obj in var_objs:
                    if pos == "body":
                        tmp = self.response.body.get(var_obj.get("key"))
                        if tmp is None:
                            logger.warning(f"Key {var_obj.get('key')} not found")
                            continue
                        if len(tmp) == 0:
                            logger.warning(f"Key {var_obj.get('key')} not found")
                            continue
                        if len(tmp) != 1:
                            raise ValueError("The key must be unique")
                        tmp = tmp[0]
                        global_vars[var_obj.get("name")] = tmp

        global_vars.save()

    def importer(self, global_vars):
        import pystache

        if self.importer_config is None:
            return

        sources = set(self.importer_config.keys())
        if "headers" in sources:
            for key, value in self.importer_config["headers"].items():
                renderer = pystache.Renderer(missing_tags="strict")
                try:
                    parse_value = renderer.render(value, global_vars)
                    self.header.add(key, parse_value)
                except pystache.context.KeyNotFoundError as e:
                    logger.error(f"Key not found: {e} - skipping adding")

        if "body" in sources:
            for key, value in self.importer_config.get("body").items():
                renderer = pystache.Renderer(missing_tags="strict")
                try:
                    parse_value = renderer.render(value, global_vars)
                    self.body.add(key, parse_value)
                except pystache.context.KeyNotFoundError as e:
                    logger.error(f"Key not found: {e} - skipping adding")


class Response:
    """
    Class for store response data
    """

    def __init__(self, response: bytes):
        if len(response.strip()) == 0:
            response = b"Failed\r\n\r\nFailed"
        self.raw_headers, self.raw_body = response.split(sep=b"\r\n\r\n", maxsplit=1)
        self.header = Header(self.raw_headers)
        self.body = Body(self.raw_body)

        first_line = self.raw_headers.split(sep=b"\r\n")[0]
        try:
            self.version, self.status_code, self.reason = first_line.split(
                sep=b" ", maxsplit=2
            )
        except ValueError:
            self.version, self.status_code, self.reason = b"", b"", b""


import socket
import ssl
from typing import Optional, Dict


def send_http_request(
    host: str,
    port: int,
    raw_req: bytes,
    timeout: float = 30.0,
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
        try:
            sock.connect((proxy_host, proxy_port))
        except ConnectionError as e:
            print(f"Proxy connection failed: {e}")
            return b""

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
