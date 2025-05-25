from uber_compose import Environment
from uber_compose import UberCompose


async def services_started(config_template: Environment,
                           compose_files: str,
                           force_restart: bool = False,
                           release_id: str | None = None,
                           parallelism_limit: int = 1,
                           ):
    response = await UberCompose().up(
        config_template=config_template,
        compose_files=compose_files,
        force_restart=force_restart,
        release_id=release_id,
        parallelism_limit=parallelism_limit
    )

    return response
