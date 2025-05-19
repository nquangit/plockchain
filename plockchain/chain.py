import yaml
from .request import Request


class Node:
    """Class for store node"""

    def __init__(self, obj: Request, prev, next):
        self.obj = obj
        self.prev = prev
        self.next = next


class RequestChain:
    """Class for RequestChain store linked list"""

    def __init__(self):
        self.head: Node | None = None
        self.tail: Node | None = None

        self.node_list = []
        self.node_dict = {}
        self.global_vars = {}
        self.proxy_config = None

    def add(self, obj, name):
        """Add object to linked list"""
        if self.head is None:
            self.head = Node(obj, None, None)
            self.tail = self.head
            self.node_list.append(self.head)
            self.node_dict[name] = self.head
        else:
            self.tail.next = Node(obj, self.tail, None)
            self.tail = self.tail.next
            self.node_list.append(self.tail)
            self.node_dict[name] = self.tail

    def run(self):
        """Run all requests"""
        curr = self.head
        while curr is not None:
            curr.obj.run(self.global_vars, self.proxy_config)
            curr = curr.next

    @staticmethod
    def parse_config(filename: str) -> object:
        """Parse yaml config file"""

        from pathlib import Path

        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(f"File {filename} not found")

        with path.open(mode="r") as f:
            data = yaml.safe_load(f)

        chain = data.get("chain")
        proxy_config = data.get("proxy", None)
        global_vars = data.get("global_vars", {})

        if not isinstance(global_vars, dict):
            raise ValueError("Global vars must be dict")

        if proxy_config is not None:
            if not isinstance(proxy_config, dict):
                raise ValueError("Proxy config must be dict")
            try:
                proxy_config.get("host")
                proxy_config.get("port")
            except AttributeError:
                raise ValueError("Proxy config must have host and port")

        if not isinstance(chain, list):
            raise ValueError("Chain not found in config file")

        base_dir = path.parent

        req_chain = RequestChain()
        # Load global vars
        req_chain.global_vars = global_vars
        req_chain.proxy_config = proxy_config

        for req in chain:
            req_conf = req.get("req")
            if not isinstance(req_conf, dict):
                raise ValueError("Request not found in config file")

            req_obj = Request.parse_request(base_dir, req_conf)

            req_chain.add(req_obj, req_conf.get("name"))

        return req_chain
