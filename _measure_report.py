import cProfile, pstats, io, time
from python_backend.research import watchlist as wl
from python_backend.research.html_report import build_data

wls = wl.list_watchlists()
wid = wls[0].id
print(f"using wid={wid} name={getattr(wls[0],'name','?')}")

pr = cProfile.Profile()
t0 = time.perf_counter()
pr.enable()
build_data(wid)
pr.disable()
print(f"COLD build_data: {(time.perf_counter()-t0)*1000:.0f} ms")

s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
ps.print_stats(35)
print(s.getvalue())
