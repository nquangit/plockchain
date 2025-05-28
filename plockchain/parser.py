import yaml
import jsonschema
from pathlib import Path


class Parser:
	@staticmethod
	def parse_config(filename: str) -> object:
		"""Parse yaml config file"""

		from .chain import RequestChain
		from pathlib import Path

		path = Path(filename)
		if not path.exists():
			raise FileNotFoundError(f"File {filename} not found")

		# Path đến file hiện tại
		current_file = Path(__file__).resolve()
		# Thư mục chứa file
		current_dir = current_file.parent

		with open(current_dir / "schema.yaml", "r") as f:
			schema = yaml.safe_load(f)

		with path.open(mode="r") as f:
			data = yaml.safe_load(f)

		try:
			jsonschema.validate(instance=data, schema=schema)
		except jsonschema.exceptions.ValidationError as e:
			print(f"Validation ERROR in '{path.name}':")
			print(e)
			exit(-1)
		except yaml.YAMLError as e:
			print(f"Lỗi khi đọc file YAML (cấu hình hoặc schema): {e}")
			exit(-1)
		except Exception as e:
			print(f"Đã xảy ra lỗi không mong muốn: {e}")
			exit(-1)

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

		req_chain: RequestChain = RequestChain()
		# Load global vars
		req_chain.global_vars.update(global_vars)
		req_chain.global_vars.load_config(global_vars.get("__persistence__", {}))

		# Load Stored variable
		try:
			with open(req_chain.global_vars.DEFAULT_FILENAME, "r") as f:
				stored_vars = yaml.safe_load(f)
				req_chain.global_vars.update(stored_vars)
		except FileNotFoundError:
			pass

		req_chain.proxy_config = proxy_config

		for req in chain:
			req_conf = req.get("req")
			if not isinstance(req_conf, dict):
				raise ValueError("Request not found in config file")

			req_obj = Parser.parse_request(base_dir, req_conf)

			req_chain.add(req_obj, req_conf.get("name"))

		# Support chain like: login
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
				req_obj = Parser.parse_request(base_dir, req_conf)
				support_chain_reqs.add(req_obj, req_conf.get("name"))

			req_chain.support_chains[support_chain] = support_chain_reqs

		return req_chain

	@staticmethod
	def parse_request(base_dir: Path, req_conf: dict) -> object:
		"""Parse request from file"""
		from .request import Request

		filename = base_dir / req_conf.get("name")
		if filename is None:
			raise ValueError("Filename is None")

		with open(file=filename, mode="rb") as req:
			data = req.read()

		export_config = req_conf.get("export", None)
		import_config = req_conf.get("import", None)

		use_tls = req_conf.get("use_tls", True)
		auto_update_content_length = req_conf.get("auto_update_content_length", True)
		timeout = req_conf.get("timeout", 30.0)

		host = req_conf.get("host")
		port = req_conf.get("port")

		if host is None or port is None:
			host = "auto"
			port = "auto"

		events = req_conf.get("events", [])

		if events is not None and not isinstance(events, list):
			raise ValueError("Event must be a list")

		for event in events:
			if not isinstance(event, dict):
				raise ValueError("Event must be a dict")
			if (
				event.get("conditions", None) is None
				or event.get("triggers", None) is None
			):
				raise ValueError("Event must have conditions and triggers")

		req = Request(
			(host, port), data, use_tls, timeout, import_config, export_config, events, auto_update_content_length
		)
		return req
