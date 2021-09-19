import json
import uuid
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

import zmq
from zmq import Socket
from zmq.utils import jsonapi

from ztimer.core import DefaultTimer, MessageTypes
from ztimer.server import TimeServer

TimedFunctionType = TypeVar("TimedFunctionType", bound=Callable[..., Any])


class ZTimer:
    def __init__(
        self,
        session_id: Optional[str] = None,
        ip: str = "localhost",
        time_server_port: int = 5555,
        results_port: int = 5556,
        start_time_server=False,
    ):
        self.session_id = session_id if session_id else str(uuid.uuid4())
        self.ip = ip
        self.time_server_port = time_server_port
        self.results_port = results_port
        self.context = zmq.Context()
        self.sender = self.context.socket(zmq.PUSH)
        self.sender.setsockopt(zmq.LINGER, 0)
        self.sender.connect(f"tcp://{ip}:{time_server_port}")
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.setsockopt(zmq.LINGER, 0)
        self.subscriber.setsockopt(zmq.SUBSCRIBE, b"")
        self.subscriber.connect(f"tcp://{ip}:{results_port}")

        if start_time_server:
            self.start_time_server()

    def start_time_server(self) -> None:
        self.time_server = TimeServer(
            ip=self.ip, sub_port=self.time_server_port, topic=self.session_id,
        )
        self.time_server.start()
        self.time_server.is_ready.wait()

    def __call__(
        self, name: Optional[str] = None
    ) -> Callable[[TimedFunctionType], DefaultTimer]:
        def decorator(f: TimedFunctionType) -> DefaultTimer:
            _f = DefaultTimer(
                callback=f,
                name=name,
                session_id=self.session_id,
                ip=self.ip,
                time_server_port=self.time_server_port,
                sender=self.sender,
            )
            return _f

        return decorator

    def _request_summary(
        self, ip: Optional[str] = None, port: Optional[int] = None,
    ) -> None:
        ip = ip if ip else self.ip
        port = port if port else self.results_port
        message = jsonapi.dumps(
            {"action": MessageTypes.summary, "port": port, "ip": ip}
        )
        self.sender.send_multipart([self.session_id.encode("ascii"), message])

    def summary(
        self,
        ip: Optional[str] = None,
        port: Optional[int] = None,
        verbose: bool = True,
    ) -> Dict[str, List[Dict[str, Union[int, float]]]]:
        ip = ip if ip else self.ip
        port = port if port else self.results_port

        self._request_summary()
        session_id, message = self.subscriber.recv_multipart()
        message = jsonapi.loads(message)
        if verbose:
            print(json.dumps(message, indent=2))

        return message

    def close(self):
        if self.time_server:
            message = jsonapi.dumps({"action": MessageTypes.terminate})
            self.sender.send_multipart(
                [self.session_id.encode("ascii"), message]
            )
            self.time_server.close()
            self.sender.close()
