# tools/snap_branch.py
import os, time, asyncio
from daytona import Daytona, DaytonaConfig, CreateSandboxFromSnapshotParams as P

d = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"]))
sb = d.create()
W = "/home/daytona/work"
print(sb.process.exec(f"mkdir -p {W} && echo step1 > {W}/log.txt && cat {W}/log.txt").result)
sb.process.exec(f"echo step2 >> {W}/log.txt")

name = f"cp-{int(time.time())}"
sb.create_snapshot(name)

t0 = time.time()
kids = [d.create(P(snapshot=name)) for _ in range(3)]
print(f"3 branches in {time.time()-t0:.1f}s")
for k in kids:
    print(k.id, "->", k.process.exec(f"cat {W}/log.txt").result)   # want step1+step2
for k in kids: d.delete(k)
d.delete(sb)