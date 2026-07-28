# Enabling Plugin in vedro.cfg.py

```python
import vedro
from uber_compose import VedroUberCompose, ComposeConfig, Environment, Service, DEFAULT_ENV_DESCRIPTION


class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True

            # Define Docker Compose services
            default_env = Environment(
                # named from docker-compose.yml
                Service("db"),
                "api",
                description=DEFAULT_ENV_DESCRIPTION
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

            # Warn if a scenario has no `env = ...` field (enabled by default)
            warn_missing_env = True
```

## Missing `env` warning

By default, the plugin logs a warning when a scenario does not define an `env` field and falls back to `default_env`.

Disable this warning if your project intentionally relies on `default_env`:

```python
class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            warn_missing_env = False
```

# Setup Uber-Compose Startup Services HealthCheck Params

Fine-tune health check parameters to ensure that your services are up and running before tests start executing. This can help avoid flaky tests due to services not being ready yet.

## HealthCheck interval and attempts
```python
from uber_compose import VedroUberCompose, ComposeConfig, Environment, Service, UpHealthPolicy

class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True

            ...

            health_policy = UpHealthPolicy(
                service_up_check_attempts=100,
                service_up_check_delay_s=3,
                ...,
            )
```

## Migrations success criteria
```python
from uber_compose import VedroUberCompose, ComposeConfig, Environment, Service, UpHealthPolicy

class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True

            ...

            health_policy = UpHealthPolicy(
                skip_migrations_errors=[b'Warning: String is empty'],  # skipped from stderr of executed migrations
            )
```
