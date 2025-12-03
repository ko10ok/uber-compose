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
```

# Setup Uber-Compose Startup Services HealthCheck Params
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
                ...
            )
```
