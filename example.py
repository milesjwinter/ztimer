import random
import time

from ztimer import ZTimer

zt = ZTimer()


@zt(name="potato")
def spud(x: str) -> str:
    time.sleep(random.uniform(0.05, 0.001))
    return x


@zt()
def fry(x: str) -> str:
    time.sleep(random.uniform(0.05, 0.001))
    return x


if __name__ == "__main__":
    zt.start_time_server()
    for _i in range(100):
        s = spud(fry(spud("tater tot")))
        f = fry(s)
    s = zt.summary()
    zt.close()
