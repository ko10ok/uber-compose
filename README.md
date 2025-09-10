
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

## 🧪 Test Examples

Run tests with the default environment:

```bash
vedro run
```

Forcefully restart environment before start:

```bash
vedro run --uc-fr
```

Use the "dev" configuration profile:

```bash
vedro run --uc-dev
```

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
