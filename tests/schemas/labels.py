from d42 import schema

from uber_compose.helpers.labels import Label

LabelsSchema = schema.dict({
    'com.docker.compose.service': schema.str,
    'com.docker.compose.project.config_files': schema.str,
    'com.docker.compose.project': schema.str,
    'com.docker.compose.project.working_dir': schema.str,

    Label.RELEASE_ID: schema.str,
    Label.ENV_ID: schema.str,
    Label.ENV_DESCRIPTION: schema.str,

    Label.TEMPLATE_SERVICE_NAME: schema.str,
    Label.SERVICE_NAME: schema.str,

Label.COMPOSE_FILES: schema.str,
    Label.COMPOSE_FILES_INSTANCE: schema.str,

    Label.ENV_CONFIG_TEMPLATE: schema.str,
    Label.ENV_CONFIG: schema.str,

    ...: ...,
})
