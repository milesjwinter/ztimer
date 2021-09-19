from multiprocessing import Event, Process
from typing import Dict, Set, Union

import zmq
from zmq import Socket
from zmq.utils import jsonapi

from ztimer.core import MessageTypes


class TimeMetric:
    def __init__(self) -> None:
        self.success_time = 0.0
        self.success_counts = 0
        self.error_time = 0.0
        self.error_counts = 0

    def increment(self, time: float, status: str) -> None:
        if status == MessageTypes.success:
            self.success_time += time
            self.success_counts += 1
        elif status == MessageTypes.error:
            self.error_time += time
            self.error_counts += 1

    def compute_stats(self) -> Dict[str, Dict[str, Union[float, int]]]:
        # TODO not this
        return {
            "success": {
                "counts": self.success_counts,
                "average": self.success_time / self.success_counts
                if self.success_counts
                else 0,
            },
            "errors": {
                "counts": self.error_counts,
                "average": self.error_time / self.error_counts
                if self.error_counts
                else 0,
            },
        }


class TimeServer(Process):
    def __init__(
        self, ip: str = "localhost", sub_port: int = 5555, topic: str = ""
    ) -> None:
        super().__init__()
        self.ip = ip
        self.sub_port = sub_port
        self.topic = topic
        self.is_ready = Event()
        self.exit_flag = Event()
        self.func_registry: Set[str] = set()
        self.metrics: Dict[str, TimeMetric] = {}

    def close(self) -> None:
        self.is_ready.clear()
        self.exit_flag.set()
        self.terminate()
        self.join()

    def run(self) -> None:
        self._run()

    def _run(self) -> None:
        self.context = zmq.Context()
        receiver = self.context.socket(zmq.PULL)
        receiver.bind(f"tcp://*:{self.sub_port}")

        publisher = self.context.socket(zmq.PUB)
        # TODO add port arg
        publisher.bind(f"tcp://*:5556")

        self.is_ready.set()
        while not self.exit_flag.is_set():
            topic, message = receiver.recv_multipart()
            message = jsonapi.loads(message)
            action = message.pop("action")
            if action == MessageTypes.log:
                func_name = message.pop("name")
                if func_name in self.func_registry:
                    self.metrics[func_name].increment(**message)
                else:
                    self.func_registry.add(func_name)
                    self.metrics[func_name] = TimeMetric()
                    self.metrics[func_name].increment(**message)

            elif action == MessageTypes.summary:
                summary = {
                    "summary": [
                        {k: v.compute_stats()}
                        for (k, v) in self.metrics.items()
                    ]
                }
                publisher.send_multipart([b"", jsonapi.dumps(summary)])
            elif action == MessageTypes.terminate:
                self.close()
