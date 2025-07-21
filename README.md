# Uber-Compose

Lightweight docker compose extension to control environment for tests

---

**Summary for README:**

---

### 1. Описание

Uber-Compose — это расширение для Docker Compose, предназначенное для управления тестовыми окружениями. Оно позволяет автоматически поднимать, настраивать и контролировать окружения для тестов, интегрируясь с фреймворком Vedro через плагин. Основная цель — упростить и ускорить подготовку инфраструктуры для end-to-end и интеграционных тестов.

---

### 2. Установка

```bash
pip install uber-compose
```

или добавить в `requirements.txt`:

```
uber-compose
```

---

### 3. Использование с Vedro

1. **Добавьте плагин в ваш `vedro.cfg.py`:**

```python
from uber_compose import VedroUberCompose, ComposeConfig, Environment, Service

class Config(vedro.Config):
    class Plugins(vedro.Config.Plugins):
        class UberCompose(VedroUberCompose):
            enabled = True
            # Определите сервисы и окружения
            default_env = Environment(
                Service("db"),
                Service("api"),
            )
            compose_cfgs = {
                "default": ComposeConfig(
                    compose_files="docker-compose.yml",
                ),
                "dev": ComposeConfig(
                    compose_files="docker-compose.yml:docker-compose.dev.yml",
                ),
            }
```

2. **Запуск тестов с управлением окружением:**

Плагин автоматически поднимет нужные сервисы перед запуском тестов и выключит их после.

3. **CLI параметры:**

- `--uc-fr` — форсировать перезапуск окружения
- `--uc-v` — уровень логирования

Продвинутые возможности:
- `--uc-default | --uc-dev` — выбрать ComposeConfig для окружения
- `--uc-external-services` — использовать внешние сервисы

---
