from uber_compose.core.utils.compose_files import read_dc_file


def parse_docker_compose_services_deps(file_paths):
    services_dict = {}

    for file_path in file_paths.split(':'):
        dc_cfg = read_dc_file(file_path)
        services = dc_cfg.get('services', {})
        for service_name, service_data in services.items():
            service_deps = set(services_dict.get(service_name, []))
            current_file_service_deps = set(service_data.get('depends_on', []))

            services_dict[service_name] = list(service_deps | current_file_service_deps)

    return services_dict
