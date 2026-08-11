#!/usr/bin/env python3
"""Warmup schwerer energie_monitor-API-Queries für Grafana-Dashboards.

Läuft im finanzen_cron-Container (Hostname energie_monitor:8080).

Usage:
  warmup_grafana_queries.py [full|short|recent]
"""
from __future__ import annotations

import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone


def main() -> int:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "full").strip().lower()
    if mode not in ("full", "short", "recent"):
        mode = "full"

    base = os.environ.get("ENERGIE_MONITOR_URL", "http://energie_monitor:8080").rstrip("/")
    timeout = int(os.environ.get("WARMUP_TIMEOUT_SEC", "180"))
    parallel = int(os.environ.get("WARMUP_PARALLEL", "2"))
    kwp = os.environ.get("PV_PEAK_KWP", "11.28")
    tz_name = os.environ.get("WARMUP_TZ", "Europe/Berlin")
    start_year = int(os.environ.get("PV_START_YEAR", "2012"))

    now = datetime.now(timezone.utc).replace(microsecond=0)
    iso = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    now_s = iso(now)
    d2 = iso(now - timedelta(days=2))
    d7 = iso(now - timedelta(days=7))
    d30 = iso(now - timedelta(days=30))
    ytd = iso(datetime(now.year, 1, 1, tzinfo=timezone.utc))
    year = now.year
    month = now.month

    urls: list[str] = []

    def add(path: str) -> None:
        urls.append(path)

    def add_current() -> None:
        add("/api/v1/metrics/haus_gesamt/current")
        add("/api/v1/metrics/pv/current")
        add("/api/v1/metrics/waermepumpe/current")

    def add_recent_windows(start: str) -> None:
        add(f"/api/v1/metrics/haus_gesamt/load-profile?start={start}&end={now_s}&interval=auto")
        add(f"/api/v1/energy/balance?start={start}&end={now_s}")
        add(f"/api/v1/metrics/haus_gesamt/timeseries?start={start}&end={now_s}&max_points=800")
        add(f"/api/v1/metrics/pv/timeseries?start={start}&end={now_s}&max_points=800")
        add(f"/api/v1/metrics/waermepumpe/timeseries?start={start}&end={now_s}&max_points=800")

    def add_aggregates(start: str) -> None:
        for m in ("haus_gesamt", "pv", "eauto", "haus_ohne_eauto", "waermepumpe"):
            add(f"/api/v1/metrics/{m}/aggregate/daily?start={start}&end={now_s}")
        for m in ("haus_gesamt", "pv"):
            add(f"/api/v1/metrics/{m}/aggregate/monthly?start={start}&end={now_s}")
        add(
            f"/api/v1/metrics/haus_gesamt/aggregate/night-daily"
            f"?start={start}&end={now_s}&time_from=22:00&time_to=06:00&timezone={tz_name}"
        )

    def add_pv_yield() -> None:
        add(
            f"/api/v1/pv/yield/summary?start_year={start_year}&end_year={year}"
            f"&timezone={tz_name}&peak_power_kwp={kwp}"
        )
        add(
            f"/api/v1/pv/yield/monthly-wide?start_year={start_year}&end_year={year}"
            f"&timezone={tz_name}&peak_power_kwp={kwp}"
        )
        add(
            f"/api/v1/pv/yield/yearly?start_year={start_year}&end_year={year}"
            f"&timezone={tz_name}&peak_power_kwp={kwp}"
        )
        add(f"/api/v1/pv/yield/summary?year={year}&timezone={tz_name}&peak_power_kwp={kwp}")
        add(
            f"/api/v1/pv/yield/summary?year={year}&month={month}"
            f"&timezone={tz_name}&peak_power_kwp={kwp}"
        )
        add(f"/api/v1/pv/yield/month?year={year}&month={month}&timezone={tz_name}")

    if mode == "recent":
        add_current()
        add_recent_windows(d2)
        add_recent_windows(d7)
    elif mode == "short":
        add_current()
        add_aggregates(d7)
        add_aggregates(d30)
        add_recent_windows(d2)
        add_recent_windows(d7)
        add(f"/api/v1/pv/yield/summary?year={year}&timezone={tz_name}&peak_power_kwp={kwp}")
        add(
            f"/api/v1/pv/yield/summary?year={year}&month={month}"
            f"&timezone={tz_name}&peak_power_kwp={kwp}"
        )
        add(f"/api/v1/pv/yield/month?year={year}&month={month}&timezone={tz_name}")
    else:
        add_current()
        add_aggregates(d30)
        add_aggregates(ytd)
        add_recent_windows(d2)
        add_recent_windows(d7)
        add_recent_windows(d30)
        add_pv_yield()

    # dedupe preserve order
    seen: set[str] = set()
    paths: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            paths.append(u)

    header = (
        f"=== warmup_grafana start {datetime.now().astimezone().isoformat(timespec='seconds')} "
        f"mode={mode} base={base} n={len(paths)} parallel={parallel} ==="
    )
    print(header, flush=True)

    def one(path: str) -> tuple[bool, str]:
        url = base + path if path.startswith("/") else path
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(url, method="GET", headers={"User-Agent": "finanzen-warmup/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp.read(64)
                code = resp.status
                ok = 200 <= code < 300
                msg = f"OK {code}" if ok else f"HTTP {code}"
        except Exception as e:  # noqa: BLE001 — cron should never crash
            ok = False
            msg = f"ERR {type(e).__name__}: {e}"
        dt = time.monotonic() - t0
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {dt:6.1f}s  {msg}  {path}"
        return ok, line

    ok_n = fail_n = 0
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        futs = [ex.submit(one, p) for p in paths]
        for fut in as_completed(futs):
            ok, line = fut.result()
            ok_n += int(ok)
            fail_n += int(not ok)
            print(line, flush=True)
        summary = f"=== warmup_grafana done ok={ok_n} fail={fail_n} total={len(paths)} ==="
        print(summary, flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
