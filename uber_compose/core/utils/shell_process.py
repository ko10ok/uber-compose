import shlex


def parse_process_command_name(command: str) -> str:
    parts = shlex.split(command)
    if parts[0] == 'sh':
        return parse_process_command_name(parts[2])

    # TODO change the way to determine process name inside docker container via script pid subgroup
    if parts[0] == 'run.sh':
        return parse_process_command_name(parts[1])

    return parts[0]
