import shlex


def parse_process_command_name(command: str) -> str:
    parts = shlex.split(command)
    if parts[0] == 'sh':
        return parse_process_command_name(parts[2])

    return parts[0]
