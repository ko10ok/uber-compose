# Lifecycle Hooks

Register callbacks that run automatically after `up()` succeeds:

```python
from uber_compose import UberCompose, UberComposeEvent

uber_compose = UberCompose()
uber_compose.on(UberComposeEvent.AFTER_UP, refresh_client, client, base_url='http://s1:8080')

await uber_compose.up(compose_files='docker-compose.yaml', config_template=my_environment)
```

`func` may be sync or async. Extra `*args`/`**kwargs` passed to `.on()` are
forwarded on every call. Multiple hooks per event run in registration order.

## Events

- `AFTER_UP` — every successful `up()` (fresh start, restart, or reuse).
- `AFTER_UPDATED_ENV_UP` — only when this `up()` restarted an environment this
  same instance had already brought up before (config/services changed since
  the last `up()`). Use it to refresh clients pointing at services that may
  have moved/restarted. Detected purely in-process (no extra docker calls);
  resets per `UberCompose()` instance, persists for the process with
  `TheUberCompose()`.

## With `TheUberCompose`

Hooks registered on the singleton are shared process-wide:

```python
from uber_compose import TheUberCompose, UberComposeEvent

TheUberCompose().on(UberComposeEvent.AFTER_UPDATED_ENV_UP, refresh_all_clients)
```
