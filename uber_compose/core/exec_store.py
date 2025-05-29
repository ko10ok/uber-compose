from uber_compose.helpers.exec_record import ExecRecord

# singleton per tests script run
EXECS: dict[str, ExecRecord] = {}
