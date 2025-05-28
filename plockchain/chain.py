import yaml
import uuid
import logging
from .request import Request

logger = logging.getLogger(__name__)


class Node:
    """Class for store node"""

    def __init__(self, obj: Request, prev: Request | None, next: Request | None):
        self.obj = obj
        self.prev = prev
        self.next = next


class GlobalVariable(dict):
    """Class for store global variables"""

    DEFAULT_FILENAME = "global_vars.yaml"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enabled = True
        self.filename = self.DEFAULT_FILENAME

    def load_config(self, config: dict):
        if config is None or not isinstance(config, dict):
            raise ValueError("Config must be dict")

        self.enabled = config.get("enabled", True)
        self.filename = config.get("filename", self.DEFAULT_FILENAME)

    def save(self):
        """Save global variables to file"""
        # Exclude object in global variable
        if not self.enabled:
            return

        string_variable = {}
        for key, value in self.items():
            if isinstance(value, str):
                string_variable[key] = value

        with open(self.filename, "w") as f:
            yaml.dump(string_variable, f)


class RequestChain:
    """Class for RequestChain store linked list"""

    def __init__(self):
        self.head: Node | None = None
        self.tail: Node | None = None

        self.node_list = []
        self.node_dict = {}
        self.global_vars = GlobalVariable({"uuid4": lambda: str(uuid.uuid4())})
        self.proxy_config = None
        self.support_chains = {}
        self.request_responses = []

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

    def run(
        self, custom_vars: dict | None = None, custom_support_chains: dict | None = None
    ):
        """Run all requests"""
        if custom_vars is not None and isinstance(custom_vars, dict):
            self.global_vars.update(custom_vars)

        if custom_support_chains is not None and isinstance(
            custom_support_chains, dict
        ):
            self.support_chains.update(custom_support_chains)

        curr = self.head
        while curr is not None:
            request_response = curr.obj.run(
                self.global_vars, self.proxy_config, self.support_chains
            )
            self.request_responses.append(request_response)
            curr = curr.next

            if self.global_vars.get("skip_the_chain", False):
                break

            if self.global_vars.get("delay_time", 0) > 0:
                import time

                logger.warning(f"Delay {self.global_vars.get('delay_time')} seconds")
                time.sleep(self.global_vars.get("delay_time"))

        self.global_vars.save()

        return self.request_responses
