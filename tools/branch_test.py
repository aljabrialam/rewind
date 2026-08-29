# tools/branch_test.py — 3 minutes, decides how we branch
import os, time
from daytona import Daytona, DaytonaConfig
d = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"]))

sb = d.create()
sb.process.exec("mkdir -p /work && echo step1 > /work/log.txt")
sb.process.exec("echo step2 >> /work/log.txt")

# Plan A: snapshot the live sandbox, create children from it
try:
    t0 = time.time()
    name = f"cp-{int(t0)}"
    sb.create_snapshot(name)
    print(f"snapshot OK in {time.time()-t0:.1f}s -> {name}")
    print("NOW: check the Daytona docs/dashboard for how to create from this snapshot")
except Exception as e:
    print("snapshot FAILED:", str(e)[:160])

# Plan B: replay — always works, no special sandbox class needed
t0 = time.time()
child = d.create()
child.process.exec("mkdir -p /work && echo step1 > /work/log.txt")   # replay history
print(f"replay child ready in {time.time()-t0:.1f}s")
print("child state:", child.process.exec("cat /work/log.txt").result)  # step1 only
d.delete(child); d.delete(sb)