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
        self.support_chains = {}

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
            curr.obj.run(self.global_vars, self.proxy_config, self.support_chains)
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
        if not isinstance(chain, list):
            raise ValueError("Chain not found in config file")

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

        # Support chain like login
        support_chains = [i for i in data.keys() if i.endswith("_chain")]
        for support_chain in support_chains:
            support_chain_reqs = RequestChain()
            support_chain_reqs.proxy_config = proxy_config
            support_chain_reqs.global_vars = req_chain.global_vars

            req_chain.support_chains[support_chain] = None
            chain = data[support_chain]
            for req in chain:
                req_conf = req.get("req")
                if not isinstance(req_conf, dict):
                    raise ValueError("Request not found in config file")
                req_obj = Request.parse_request(base_dir, req_conf)
                support_chain_reqs.add(req_obj, req_conf.get("name"))

            req_chain.support_chains[support_chain] = support_chain_reqs

        return req_chain
