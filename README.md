🚀 Uber-Compose — Lightweight Docker Compose Extension for Test Environments

## 🔧 Overview

Uber-Compose is a lightweight extension for managing test environments with Docker Compose. It simplifies infrastructure management for end-to-end (E2E) and integration testing by automatically provisioning services before tests begin and cleaning them up afterward.

It integrates seamlessly with the Vedro testing framework (https://vedro.io) via a dedicated plugin.

With Uber-Compose, you can define test environments, handle multiple docker-compose configurations, and focus entirely on your test scenarios — the infrastructure is managed for you.

---

## ✨ Key Features

- 🚀 Automated setup and teardown of Docker Compose services
- 🔌 Native plugin integration with Vedro (https://vedro.io)
- 🧩 Supports multiple docker-compose profiles
- 🛠️ Flexible command-line control
- 💻 Works in both local dev and CI/CD environments

---

## 📦 Installation

Install via pip:

```bash
pip install uber-compose
```

Or add to your requirements.txt:

```
uber-compose
```

---

## 🛠️ How to Use with Vedro

### 1. Enable the Plugin in vedro.cfg.py

```python
from uber_compose import VedroUberCompose, ComposeConfig, Environment, Service

class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True

            # Define Docker Compose services
            default_env = Environment(
                # named from docker-compose.yml
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

### 2. Run Your Tests

Uber-Compose will:

- Automatically start necessary services
- Ensure they are fully running before tests begin
- Restart conflicting services if configurations changed

Everything is handled for you — zero manual setup!

### 3. Command Line Options

You can customize behavior dynamically:

- --uc-fr — Force restart of services
- --uc-v — Set logging verbosity level
- --uc-default / --uc-dev — Choose defined ComposeConfigs

---

## 🎯 Environment-Specific Test Configurations

You can define custom environments for specific test scenarios and Uber-Compose will automatically provision the required services when running those tests.

### Define Custom Environments

Create environment configurations that match your test requirements:

```python
# envs.py
from uber_compose import Environment, Service

WEB_S3_MOCKMQ = Environment(
    Service("s3"),
    Service("mock_mq"),
    Service("cli"),
    Service("api")
)

MINIMAL_DB_ONLY = Environment(
    Service("database")
)
```

### Use in Your Tests

Simply specify the environment in your test scenario:

```python
# test.py
import vedro
from envs import WEB_S3_MOCKMQ

class Scenario(vedro.Scenario):
    subject = 'consume contest mq message without message'
    env = WEB_S3_MOCKMQ

    def when_message_consumed(self):
        # Your test logic here
        pass
```

### Automatic Environment Management

Run your test file and the required environment will be set up automatically:

```bash
vedro run test_path.py
```

Uber-Compose will:
- ✅ Detect the custom environment specified in your test
- 🚀 Start only the required services (s3, mock_mq, cli, api)
- ⏱️ Wait for all services to be healthy before running the test
- 🧹 Clean up resources after test completion

This approach ensures each test gets exactly the infrastructure it needs, improving test isolation and reducing resource usage.

---

## ✔️ Ideal For

- ✅ End-to-End (E2E) testing
- 🔗 Integration testing
- 🧪 Local development & reproducible CI pipelines
- 🎯 Structured tests with Vedro (https://vedro.io)

---

## 🤝 Contribute

We welcome pull requests, feature requests, and community feedback!

📍 Source Repository:  
https://github.com/ko10ok/uber-compose

---

## 🧰 One Command. Fully Managed Environments.
