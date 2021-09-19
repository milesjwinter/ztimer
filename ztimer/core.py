import time
from typing import Any, Callable, Optional

import zmq
from zmq import Context, Socket
from zmq.utils import jsonapi


class MessageTypes:
    success: str = "SUCCESS"
    error: str = "ERROR"
    log: str = "LOG"
    summary: str = "SUMMARY"
    terminate: str = "TERMINATE"


class DefaultTimer:
    def __init__(
        self,
        callback: Callable[..., Any],
        name: Optional[str] = None,
        session_id: str = "",
        ip: str = "localhost",
        time_server_port: int = 5555,
        sender: Socket = zmq.Context().socket(zmq.PUSH),
    ) -> None:
        self.callback = callback
        self.name = name if name else callback.__name__
        self.session_id = session_id.encode("ascii")
        self.ip = ip
        self.time_server_port = time_server_port
        self.message_types = MessageTypes()
        self.sender = sender

    def _log_time(
        self, time: float, message_type: str, action: str = MessageTypes.log
    ) -> None:
        message = jsonapi.dumps(
            dict(name=self.name, time=time, status=message_type, action=action)
        )
        self.sender.send_multipart([self.session_id, message])

    def __call__(self, *args, **kwargs) -> Any:
        start = time.time()
        try:
            x = self.callback(*args, **kwargs)
            delta_t = time.time() - start
            self._log_time(delta_t, self.message_types.success)
        except Exception as e:
            delta_t = time.time() - start
            self._log_time(delta_t, self.message_types.error)
            raise e
        return x
