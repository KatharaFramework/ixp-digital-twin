import logging

from .action import Action

WARNING: int = 2
SUCCESS: int = 1
ERROR: int = 0


class ActionResult:
    __slots__ = ['action', 'results']

    def __init__(self, action: Action) -> None:
        self.action: Action = action
        self.results: list[dict] = []

    def add_result(self, status: int, reason: str | None = None, data: str | None = None) -> None:
        self.results.append({'status': status, 'reason': reason, 'data': data})

    def passed(self) -> bool:
        return len(self.results) == 0 or not any([x['status'] == ERROR for x in self.results])

    def print(self, level: int) -> None:
        for result in self.results:
            if result['status'] > level:
                continue

            reason_str = f"[{self.action.display_name()}] {result['reason']}" if result['reason'] else \
                f"[{self.action.display_name()}] " + ("Passed" if result else "Failed") + " (No Message)."
            data_str = f"\nDetails:\n{result['data']}" if result['data'] else ""
            logging_str = f"{reason_str}{data_str}"

            if result['status'] == WARNING:
                logging.warning(logging_str)
            elif result['status'] == SUCCESS:
                logging.success(logging_str)
            elif result['status'] == ERROR:
                logging.error(logging_str)
