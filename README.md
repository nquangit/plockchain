## Overview

Plockchain is a lightweight, configurable automation tool designed to help web pentesters streamline their HTTP-based testing workflows. With Plockchain, you can define a sequence of HTTP requests (a "chain"), leverage proxy settings, extract and manipulate data in-flight, and easily integrate dynamic variables into subsequent requests. Whether you need to automate a login flow to fetch a token, or orchestrate a multi-step sequence to probe various endpoints, Plockchain has you covered.

## Key Features

-   **Configurable Flow**: Define multi-step HTTP chains in a simple YAML file.
-   **Proxy Support**: Route requests through an HTTP/SOCKS proxy for traffic inspection or access.
-   **Data Extraction & Injection**: Extract fields from responses (e.g., JSON bodies via `jq`-style selectors) and inject them into later requests.
-   **TLS & Timeout Controls**: Customize TLS on/off per request and set individual timeouts.
-   **Templating**: Use Mustache-style placeholders (`{{variable}}`) to render headers, URLs, and bodies dynamically.
-   **Lightweight & Extensible**: Built in Python with minimal dependencies, easy to extend for custom extractors or request types.

## Prerequisites

-   Python 3.8 or higher
-   `pip` for installing dependencies

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/nquangit/plockchain.git
    cd plockchain
    ```

2. Install required packages:

    ```bash
    pip install -r requirements.txt
    ```

## Configuration

Plockchain is driven by a YAML configuration file. Below is a sample configuration showing global variables, proxy settings, and a request chain:

```yaml
# File: config.yaml
---
---
global_vars:
    key: value

proxy:
    host: 127.0.0.1
    port: 8080

chain:
    - req:
          name: profile
          use_tls: true
          # Auto mode will get the host from the Host header
          host: auto
          # Auto mode will get the port base-on use_tls value (80 or 443)
          port: auto
          # Timeout in seconds (default: 30.0)
          timeout: 5.0

          event:
              conditions:
                  status: 401
              triggers:
                  chain: auth_chain

          import:
              headers:
                  Authorization: "Bearer {{token}}"

# Support chain must end with _chain suffix
auth_chain:
    - req:
          name: login
          host: api.taskspace.com.vn
          port: 443
          timeout: 5.0
          export:
              response:
                  body:
                      var:
                          name: token
                          # Key access with jq for json response with unique key
                          key: ".data"
```

### Configuration Fields

-   `global_vars`: Define key/value pairs available throughout the chain.
-   `proxy`: Optional proxy settings (`host`, `port`).
-   `chain`: An ordered list of steps; each step can be a `req` (HTTP request).

    -   `name`: Identifier for the step; used when exporting variables.
    -   `use_tls`: `true` for HTTPS, `false` for HTTP.
    -   `host`/`port`: Target host and port (support `auto`).
    -   `timeout`: Request timeout in seconds.
    -   `export`: Extract data from response. Currently supports `body` JSON extraction with a `key` selector.
    -   `import`: Inject variables into headers, query parameters, or body.

## Usage

Run Plockchain by pointing it to your YAML config file:

```bash
# Future
python plockchain.py --config config.yaml
```

-   Use `--verbose` for detailed logging.
-   Add `--no-proxy` to bypass proxy settings.

### Example Workflow

1. **Login** capturing a JWT token.
2. **Fetch** protected resource using the extracted token.
3. **Process** or **save** the final output as needed.

```bash
python plockchain.py -c config.yaml -v
```

## Extending Plockchain

-   **Custom Extractors**: Add support for XML, regex, or HTML parsing by extending the `exporters` module.
-   **Additional Steps**: Implement new step types (e.g., file uploads, GraphQL requests) in the `steps` directory.

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit your changes and push to your branch.
4. Open a Pull Request detailing your improvements.

Please adhere to the existing code style and include unit tests for new features.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

_Happy pentesting!_
