🚀 Uber-Compose — Lightweight Docker Compose Extension for Test Environments

Overview 🔧

Uber-Compose is a lightweight extension for managing test environments with Docker Compose. It is designed to simplify infrastructure management for end-to-end (E2E) and integration testing by automatically provisioning services before tests begin and cleaning them up after.

It integrates seamlessly with the Vedro testing framework (https://vedro.io) via a dedicated plugin.

With Uber-Compose, you can define test environments, manage multiple docker-compose configurations, and focus entirely on your test scenarios — the infrastructure is handled for you.

Key Features

- Automated setup and teardown of Docker Compose services
- Native plugin integration with Vedro (https://vedro.io)
- Support for multiple docker-compose profiles
- Flexible command-line control
- Works in both local dev and CI/CD environments

📦 Installation

Install via pip:

```bash
pip install uber-compose
```

Or add to your requirements.txt:

```
uber-compose
```

🛠️ How to Use with Vedro

1. Enable the plugin in vedro.cfg.py:

```python
from uber_compose import VedroUberCompose, ComposeConfig, Environment, Service

class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True

            # Define Docker Compose services
            default_env = Environment(
                # named from docker-compose.yml-s
                Service("db"),
                # or simply
                "api",
            )

            # Define Compose profiles
            compose_cfgs = {
                DEFAULT_COMPOSE: ComposeConfig(
                    compose_files="docker-compose.yml",
                ),
                "dev": ComposeConfig(
                    compose_files="docker-compose.yml:docker-compose.dev.yml",
                ),
            }
```

2. Run your tests:

Uber-Compose will automatically launch the required services, checks everything is up before the tests begin, reup services if services configurations incompatible with test. Everything is managed for you.

3. Command Line Options

You can customize behavior on the fly using these flags:

- --uc-fr — Force a restart of services
- --uc-v — Set logging verbosity level
- --uc-default / --uc-dev — Select predefined ComposeConfig

🧪 Test Examples

Basic test run using the default environment:

```bash
vedro run
```

Force restart the environment:

```bash
vedro run --uc-fr
```

Use an alternate configuration:

```bash
vedro run --uc-dev
```

✔️ Ideal For

- End-to-End (E2E) testing
- Integration testing
- Local development and CI/CD pipelines
- Teams using Vedro (https://vedro.io) for structured testing

🤝 Contribute

We welcome pull requests, issues, and discussions!
Source Repository: [https://github.com/your-org/uber-compose](https://github.com/ko10ok/uber-compose)

🧰 One Command. Fully Managed Environments.
