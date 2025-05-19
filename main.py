from plockchain import RequestChain

# Request.parse_request("test/raw")

import yaml

# with open("test/conf.yaml") as f:
#     data = yaml.safe_load(f)


chain: RequestChain = RequestChain.parse_config("test/conf.yaml")

chain.run()

# print(chain.head)

