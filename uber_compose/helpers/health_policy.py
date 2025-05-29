from dataclasses import dataclass


@dataclass
class UpHealthPolicy:
    wait_for_healthy_in_between: bool = True
    wait_for_healthy_after_all: bool = True
    service_up_check_attempts: int = 100
    service_up_check_delay_s: int = 3

    pre_check_delay_s: float = 0
