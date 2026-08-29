# tools/fork_test.py
import inspect, os
from daytona import Daytona, DaytonaConfig
d = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"]))
print("create signature:", inspect.signature(d.create))

sb = d.create()
sb.process.exec("echo state-marker > /tmp/marker.txt")
try:
    child = sb.fork()
except Exception as e:
    print("fork() failed:", str(e)[:200])
    child = sb._experimental_fork()
print("child id:", child.id)
print("child sees parent state:", child.process.exec("cat /tmp/marker.txt").result)
d.delete(child); d.delete(sb)