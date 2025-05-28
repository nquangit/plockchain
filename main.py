from plockchain import Parser, RequestChain


# Request.parse_request("test/raw")

import yaml

# with open("test/conf.yaml") as f:
#     data = yaml.safe_load(f)


chain: RequestChain = Parser.parse_config("test/conf.yaml")

chain.run(custom_vars={})

# print(chain.head)

