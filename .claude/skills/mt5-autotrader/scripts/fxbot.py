#!/usr/bin/env python3
"""fxbot - command line for the MT5 autotrader skill. Every command prints JSON.

    python fxbot.py doctor        preflight: is everything ready to trade?
    python fxbot.py start         launch the bot in the background
    python fxbot.py status        health, account, risk state, open trades
    python fxbot.py stop          stop the bot (add --close-all to flatten)

Run `python fxbot.py --help` for the full list.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fxbot import __version__, backtest as bt, report as rep  # noqa: E402
from fxbot import config as cfgmod  # noqa: E402
from fxbot.engine import MIN_BARS, Engine  # noqa: E402
from fxbot.store import Store  # noqa: E402
from fxbot.timeutil import from_ts, iso, market_open, utcnow  # noqa: E402

TASK_NAME = "MT5Autotrader-Watchdog"


def out(obj, code: int = 0):
    if sys.stdout is not None:                  # pythonw.exe (background on Windows) has no stdout
        print(json.dumps(obj, indent=2, default=str))
    sys.exit(code)


def fail(msg: str, **extra):
    out({"ok": False, "error": msg, **extra}, 1)


def get_mt5():
    try:
        import MetaTrader5 as mt5  # type: ignore
        return mt5
    except ImportError as exc:
        fail("the MetaTrader5 Python package is not available",
             fix="On the Windows machine that runs the MT5 terminal: python -m pip install -r requirements.txt",
             detail=str(exc), platform=sys.platform)


def make_engine(args, console: bool = False) -> Engine:
    store = Store(cfgmod.home_dir())
    cfg = cfgmod.load_config(store.home)
    log = store.logger(console=console)
    if os.environ.get("FXBOT_SIM") == "1":
        # Test/demonstration only: a simulated broker with random prices. Never real trading.
        from fxbot.selftest import build_sim
        sim = build_sim()
        sim.set_time(int(next(iter(sim.data.values()))["time"][-2]) + 5)
        return Engine(sim, cfg, store, clock=lambda: from_ts(sim.now), log=log)
    return Engine(get_mt5(), cfg, store, log=log)


# ------------------------------------------------------------------ commands
def cmd_init(args):
    home = cfgmod.home_dir()
    over = cfgmod.load_overrides(home)
    if args.profile:
        over["profile"] = args.profile
    cfgmod.save_overrides(over, home)
    cfg = cfgmod.load_config(home)
    out({"ok": True, "home": str(home), "profile": cfg["profile"], "risk": cfg["risk"], "live": cfg["live"]})


def cmd_config(args):
    cfg = cfgmod.load_config()
    out({"home": str(cfgmod.home_dir()), "overrides": cfgmod.load_overrides(), "effective": cfg,
         "hard_caps": cfgmod.HARD_CAPS})


def cmd_set(args):
    try:
        value = json.loads(args.value)
    except json.JSONDecodeError:
        value = args.value
    if args.key.startswith("live."):
        fail("live trading is changed only with the `live` command")
    cfgmod.set_override(args.key, value)
    cfg = cfgmod.load_config()
    store = Store(cfgmod.home_dir())
    if store.bot_alive():
        store.push_command({"op": "reload"})
    node = cfg
    for k in args.key.split("."):
        node = node[k]
    out({"ok": True, "key": args.key, "effective_value": node, "cap_notes": cfg["_cap_notes"],
         "applied": "the running bot reloads it on its next cycle" if store.bot_alive() else "used on next start"})


def cmd_doctor(args):
    checks = []

    def add(name, ok, detail, fix=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, **({"fix": fix} if fix and not ok else {})})

    store = Store(cfgmod.home_dir())
    cfg = cfgmod.load_config(store.home)
    add("config", not cfg["_cap_notes"], "; ".join(cfg["_cap_notes"]) or f"profile {cfg['profile']}, risk caps respected",
        "values above the hard caps were clamped; lower them in config.json")
    if os.environ.get("FXBOT_SIM") == "1":
        add("python package", True, "SIMULATED broker (FXBOT_SIM=1): test mode, not real trading")
    else:
        try:
            import MetaTrader5 as mt5  # type: ignore
            add("python package", True, f"MetaTrader5 {getattr(mt5, '__version__', '?')} on Python {sys.version.split()[0]}")
        except ImportError as exc:
            add("python package", False, f"MetaTrader5 not importable on {sys.platform}: {exc}",
                "needs Windows with the MT5 terminal installed; then: python -m pip install -r requirements.txt")
            out({"ready": False, "mode": None, "checks": checks}, 1)

    eng = make_engine(args)
    try:
        eng.connect()
        add("terminal", True, "attached to the MT5 terminal")
    except Exception as exc:
        add("terminal", False, str(exc), "open MetaTrader 5, log in to the trading account, then run doctor again")
        out({"ready": False, "mode": None, "checks": checks}, 1)

    b = eng.broker
    acct, term = b.account(), b.terminal()
    add("broker connection", term.get("connected", False), f"{acct.get('company')} / {acct.get('server')}",
        "the terminal is offline: check internet/broker login in MT5")
    add("account", True, f"login {acct.get('login')} ({acct['mode'].upper()}), {acct.get('balance')} {acct.get('currency')}, "
        f"leverage 1:{acct.get('leverage')}")
    add("algo trading", term.get("trade_allowed", False), "Algo Trading button is " + ("ON" if term.get("trade_allowed") else "OFF"),
        "click the 'Algo Trading' button in the MT5 toolbar (it must turn green)")
    if term.get("tradeapi_disabled", False):
        add("python trading api", False, "MT5 blocks trading from external Python programs",
            "MT5: Tools > Options > Expert Advisors > untick 'Disable algo trading via external Python API'")
    add("account permissions", acct.get("trade_allowed", True) and acct.get("trade_expert", True),
        "trading and expert advisors allowed" if acct.get("trade_allowed", True) and acct.get("trade_expert", True)
        else "this login cannot trade automatically", "log in with the master (not investor) password / ask the broker")
    if acct.get("margin_mode") == 0:
        add("account netting mode", False, "netting account: the bot will skip symbols where you hold manual positions", "prefer a hedging account")
    if acct.get("fifo_close"):
        add("fifo rule", False, "FIFO account: stops on multiple positions may be restricted", "use a non-FIFO account")

    optional = set(cfgmod.OPTIONAL_METALS)
    missing = [s for s in b.unresolved if s not in optional]
    add("symbols", len(b.map) >= 5, f"{len(b.map)} instruments mapped" + (f"; not offered by this broker: {missing}" if missing else ""),
        "set symbol_map in config.json for symbols with unusual names")

    short = []
    for canon in b.map:
        bars = b.bars(canon, cfg["timeframe"], int(cfg["history_bars"]))
        if bars is None or len(bars["time"]) < MIN_BARS:
            short.append(canon)
    add("price history", not short, f"enough bars on {len(b.map) - len(short)} of {len(b.map)} symbols" +
        (f"; still loading: {short}" if short else ""), "open those charts once in MT5 (H1) so history downloads, then retry")

    rp = cfg["risk"]
    try:
        fit = eng.min_lot_check()
        if fit["instruments"]:
            add("account size vs minimum lot", fit["tradable"] >= max(1, fit["instruments"] // 2),
                f"{fit['tradable']} of {fit['instruments']} traded instruments fit the {rp['risk_per_trade_pct']}% risk "
                f"budget at the minimum lot; about {fit['equity_for_half']:,.0f} {acct.get('currency')} of equity makes "
                f"half of them tradable",
                "the account is small for these stop distances: use a cent/micro-lot account, deposit more, or raise "
                "risk.risk_per_trade_pct (hard cap 2%) only with the owner's consent")
    except Exception as exc:
        add("market data", False, f"analysis failed: {type(exc).__name__}: {exc}")

    now = utcnow()
    eng.news.refresh(now)
    ns = eng.news.status(now)
    add("news calendar", ns["usable"] or not ns["enabled"], f"{ns['events']} events cached" if ns["usable"] else f"unavailable: {ns['error']}",
        "calendar host unreachable; trading continues without the news filter (fail_mode=allow)")

    mode, why = eng.trade_mode(acct, term)
    gate = rep.live_gate(store.read("trades"))
    hard = [c for c in checks if not c["ok"] and c["check"] in ("terminal", "broker connection", "algo trading",
                                                              "account permissions", "symbols", "python package",
                                                              "python trading api")]
    b.shutdown()
    out({"ready": not hard, "mode": mode, "mode_reason": why, "market_open": market_open(now),
         "live": cfg["live"], "live_gate": gate, "bot_running": store.bot_alive(), "home": str(store.home),
         "checks": checks}, 0 if not hard else 1)


def cmd_scan(args):
    eng = make_engine(args)
    rows = eng.snapshot()
    acct = eng.broker.account()
    mode, why = eng.trade_mode(acct, eng.broker.terminal())
    eng.news.refresh(utcnow())
    res = {"time": iso(), "mode": mode, "mode_reason": why, "instruments": len(rows),
           "signals": [r for r in rows if r["signal"]],
           "upcoming_high_impact_news": eng.news.upcoming(utcnow(), 24),
           "market": rows if args.all else rows[: args.top]}
    eng.broker.shutdown()
    out(res)


def cmd_cycle(args):
    eng = make_engine(args, console=True)
    res = eng.cycle()
    eng.broker.shutdown()
    out(res)


def cmd_run(args):
    store = Store(cfgmod.home_dir())
    try:
        eng = make_engine(args, console=args.console)
    except SystemExit:
        # Startup failed before the loop (e.g. MetaTrader5 package missing): leave a trace for `start`/`status`.
        store.logger().error("bot could not start: MetaTrader5 package unavailable on %s", sys.platform)
        store.write_heartbeat({"status": "error", "error": "MetaTrader5 Python package unavailable; run doctor"})
        raise
    if store.stop_path.exists():
        store.stop_path.unlink()
    eng.run()


def _python_background() -> str:
    exe = Path(sys.executable)
    if os.name == "nt":
        pyw = exe.with_name("pythonw.exe")
        if pyw.exists():
            return str(pyw)
    return str(exe)


def _spawn(home: Path) -> int:
    cmd = [_python_background(), str(Path(__file__).resolve()), "--home", str(home), "run"]
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    if os.name == "nt":
        detached, new_group, breakaway = 0x00000008, 0x00000200, 0x01000000
        try:
            return subprocess.Popen(cmd, creationflags=detached | new_group | breakaway, **kw).pid
        except OSError:
            return subprocess.Popen(cmd, creationflags=detached | new_group, **kw).pid
    return subprocess.Popen(cmd, start_new_session=True, **kw).pid


def cmd_start(args):
    store = Store(cfgmod.home_dir())
    if store.bot_alive():
        out({"ok": True, "already_running": True, "heartbeat": store.read_heartbeat()})
    if store.stop_path.exists():
        store.stop_path.unlink()
    store.set_desired("running")
    t0 = time.time()
    pid = _spawn(store.home)
    while time.time() - t0 < args.wait:
        hb = store.read_heartbeat()
        if hb and float(hb.get("ts", 0)) >= t0 - 1:
            out({"ok": hb.get("status") == "ok", "pid": hb.get("pid"), "heartbeat": hb,
                 "log": str(store.log_dir / "fxbot.log")})
        time.sleep(1)
    out({"ok": False, "pid": pid, "error": "no heartbeat yet; read the log for the reason",
         "log": str(store.log_dir / "fxbot.log")}, 1)


def cmd_stop(args):
    store = Store(cfgmod.home_dir())
    store.set_desired("stopped")
    was_running = store.bot_alive()
    store.stop_path.write_text(iso())
    stopped = not was_running
    t0 = time.time()
    while was_running and time.time() - t0 < 90:
        hb = store.read_heartbeat()
        if hb and hb.get("status") == "stopped":
            stopped = True
            break
        time.sleep(1)
    closed = None
    if args.close_all:
        eng = make_engine(args)
        closed = eng.close_positions(reason="kill switch")
        eng.broker.shutdown()
    out({"ok": stopped, "was_running": was_running, "closed": closed,
         "note": "open positions keep their server-side stop-loss" if not args.close_all else "all bot positions were closed"})


def cmd_status(args):
    store = Store(cfgmod.home_dir())
    cfg = cfgmod.load_config(store.home)
    hb = store.read_heartbeat()
    state = store.load_state()
    age = round(utcnow().timestamp() - float(hb["ts"]), 1) if hb else None
    res = {"running": store.bot_alive(), "desired": store.desired(), "heartbeat_age_sec": age, "heartbeat": hb,
           "positions": state["positions"], "risk_state": state["risk"], "profile": cfg["profile"],
           "live": cfg["live"], "live_gate": rep.live_gate(store.read("trades")),
           "recent_decisions": store.read("decisions", 8), "home": str(store.home)}
    if args.live:
        eng = make_engine(args)
        eng.ensure_connected()
        res["broker_positions"] = [{k: p[k] for k in ("ticket", "canon", "dir", "volume", "price_open", "sl", "tp", "profit")}
                                   for p in eng.broker.positions()]
        res["account"] = {k: v for k, v in eng.broker.account().items()
                          if k in ("login", "server", "mode", "balance", "equity", "margin_level", "currency")}
        eng.broker.shutdown()
    out(res)


def _control(args, cmd: dict, note: str):
    store = Store(cfgmod.home_dir())
    if store.bot_alive():
        store.push_command(cmd)
        out({"ok": True, "queued": cmd, "note": note + " (applied on the bot's next cycle)"})
    if cmd["op"] == "close":
        eng = make_engine(args)
        res = eng.close_positions(symbol=cmd.get("symbol"), ticket=cmd.get("ticket"))
        eng.broker.shutdown()
        out({"ok": all(r["ok"] for r in res), "closed": res})
    eng = Engine(None, cfgmod.load_config(store.home), store)     # offline: edit the saved state directly
    eng.apply_commands([cmd])
    store.save_state(eng.state)
    out({"ok": True, "applied": cmd, "note": note})


def cmd_pause(args):
    _control(args, {"op": "pause"}, "no new entries; open positions are still managed")


def cmd_resume(args):
    if args.reset_halt:
        _control(args, {"op": "reset_halt"}, "drawdown halt cleared; drawdown is measured from current equity")
    _control(args, {"op": "resume"}, "entries enabled again")


def cmd_veto(args):
    until = utcnow().timestamp() + args.hours * 3600.0
    _control(args, {"op": "veto", "symbol": args.symbol.upper(), "until": until, "reason": args.reason},
             f"no entries in {args.symbol.upper()} for {args.hours}h")


def cmd_unveto(args):
    _control(args, {"op": "unveto", "symbol": args.symbol.upper()}, "veto removed")


def cmd_close(args):
    if not (args.all or args.symbol or args.ticket):
        fail("say what to close: --all, --symbol EURUSD or --ticket 123")
    _control(args, {"op": "close", "symbol": args.symbol, "ticket": args.ticket}, "closing")


def cmd_report(args):
    store = Store(cfgmod.home_dir())
    trades = store.read("trades")
    res = rep.build(trades, args.days, iso())
    res["live_gate"] = rep.live_gate(trades)
    res["risk_state"] = store.load_state()["risk"]
    out(res)


def cmd_live(args):
    store = Store(cfgmod.home_dir())
    cfg = cfgmod.load_config(store.home)
    gate = rep.live_gate(store.read("trades"))
    if args.disable:
        over = cfgmod.load_overrides(store.home)
        over["live"] = {"enabled": False, "login": None, "authorized_at": None}
        cfgmod.save_overrides(over, store.home)
        if store.bot_alive():
            store.push_command({"op": "reload"})
        out({"ok": True, "live": over["live"], "note": "real-money trading disabled"})
    if not args.enable:
        out({"live": cfg["live"], "live_gate": gate})
    if not args.login:
        fail("--login <account number> is required so the authorisation is tied to one account")
    if not args.owner_confirmed:
        fail("real-money trading needs the account owner's explicit go-ahead in this conversation; "
             "pass --owner-confirmed only after they gave it", live_gate=gate)
    if not gate["passed"] and not args.override_validation:
        fail("the strategy has not yet proven itself on demo: " + gate["reason"], live_gate=gate,
             fix="keep running on a demo account, or pass --override-validation if the owner, having seen these "
                 "numbers, explicitly insists")
    over = cfgmod.load_overrides(store.home)
    over["live"] = {"enabled": True, "login": int(args.login), "authorized_at": iso(),
                    "validation_overridden": bool(not gate["passed"])}
    cfgmod.save_overrides(over, store.home)
    if store.bot_alive():
        store.push_command({"op": "reload"})
    out({"ok": True, "live": over["live"], "live_gate": gate,
         "note": "orders will be sent on the REAL account with this login only"})


def cmd_backtest(args):
    cfg = cfgmod.load_config()
    offset = 0
    if args.csv:
        data = bt.load_csv_dir(args.csv, cfg["symbols"])
        offset = int(args.utc_offset_hours * 3600)
        source = f"csv:{args.csv}"
    else:
        eng = make_engine(args)
        eng.connect()
        data = {}
        for canon in eng.broker.map:
            bars = eng.broker.bars(canon, cfg["timeframe"], args.bars)
            if bars is not None and len(bars["time"]) >= MIN_BARS:
                data[canon] = bars
        ticks = [eng.broker.tick(c) for c in list(eng.broker.map)[:8]]
        server_now = max((int(t.time) for t in ticks if t), default=0)
        if server_now and market_open(utcnow()):
            offset = int(round((server_now - time.time()) / 1800.0)) * 1800
        elif args.utc_offset_hours:
            offset = int(args.utc_offset_hours * 3600)
        else:
            offset = 2 * 3600                       # most brokers run GMT+2/+3
        source = f"mt5:{eng.broker.account().get('server')}"
        eng.broker.shutdown()
    if not data:
        fail("no price history to test on")
    res = bt.run(data, cfg, cost_mult=args.cost_mult, utc_offset_sec=offset, stop_on_halt=not args.ignore_halt)
    trades = res["trades"]
    halves = {}
    if len(trades) >= 20:
        t0, t1 = trades[0]["t_in"], trades[-1]["t_in"]
        mid = t0 + 0.6 * (t1 - t0)
        for name, part in (("first_60pct", [t for t in trades if t["t_in"] < mid]),
                           ("last_40pct", [t for t in trades if t["t_in"] >= mid])):
            rs = [t["r"] for t in part]
            halves[name] = {"trades": len(rs), "avg_r": round(sum(rs) / len(rs), 3) if rs else None}
    first = min(int(b["time"][0]) for b in data.values())
    last = max(int(b["time"][-1]) for b in data.values())
    out({"source": source, "symbols": len(data), "period": [iso(from_ts(first)), iso(from_ts(last))],
         "profile": cfg["profile"], "cost_multiplier": args.cost_mult, "stats": res["stats"], "halted": res["halted"],
         "consistency": halves, "by_setup": bt.breakdown(trades, "setup"), "by_exit": bt.breakdown(trades, "reason"),
         "by_symbol": bt.breakdown(trades, "symbol"),
         "caveats": ["no swaps/overnight financing (matters for multi-day holds)", "no news filter",
                     "fixed spread assumptions, not recorded spreads", "past results do not predict future results"]})


def cmd_watchdog(args):
    store = Store(cfgmod.home_dir())
    desired, alive = store.desired(), store.bot_alive(max_age=180)
    if desired != "running" or store.stop_requested() or alive:
        out({"ok": True, "action": "none", "desired": desired, "alive": alive})
    pid = _spawn(store.home)
    store.logger().warning("watchdog restarted the bot (pid %s)", pid)
    out({"ok": True, "action": "restarted", "pid": pid})


def cmd_autostart(args):
    if os.name != "nt":
        fail("autostart uses the Windows Task Scheduler; on this OS run `fxbot.py start` from your own service manager")
    if args.remove:
        r = subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], capture_output=True, text=True)
        out({"ok": r.returncode == 0, "output": (r.stdout + r.stderr).strip()})
    if args.install:
        home = cfgmod.home_dir()
        tr = f'"{_python_background()}" "{Path(__file__).resolve()}" --home "{home}" watchdog'
        if len(tr) > 250:                           # schtasks limits /TR to 261 characters
            launcher = home / "watchdog.cmd"
            launcher.write_text(f"@echo off\r\n{tr}\r\n")
            tr = f'"{launcher}"'
        r = subprocess.run(["schtasks", "/Create", "/TN", TASK_NAME, "/SC", "MINUTE", "/MO", "5", "/F", "/TR", tr],
                           capture_output=True, text=True)
        out({"ok": r.returncode == 0, "task": TASK_NAME, "command": tr, "output": (r.stdout + r.stderr).strip(),
             "note": "every 5 minutes Windows restarts the bot if it should be running and is not (also after reboot/login)"},
            0 if r.returncode == 0 else 1)
    r = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], capture_output=True, text=True)
    out({"installed": r.returncode == 0, "output": (r.stdout + r.stderr).strip()})


def cmd_selftest(args):
    from fxbot.selftest import run_selftest
    res = run_selftest(hours=args.hours)
    out(res, 0 if res["passed"] else 1)


def main():
    ap = argparse.ArgumentParser(prog="fxbot", description="MT5 Forex & metals autotrader")
    ap.add_argument("--home", help="data directory (default ~/.mt5-autotrader or $FXBOT_HOME)")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.set_defaults(fn=fn)
        return p

    p = add("init", cmd_init, "create the data directory / choose the risk profile")
    p.add_argument("--profile", choices=list(cfgmod.PROFILES))
    add("config", cmd_config, "show the effective configuration and hard caps")
    p = add("set", cmd_set, "change one setting, e.g. set risk.risk_per_trade_pct 0.75")
    p.add_argument("key")
    p.add_argument("value")
    add("doctor", cmd_doctor, "preflight checks with a fix for each problem")
    p = add("scan", cmd_scan, "analyse every chart now and list signals (sends no orders)")
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--all", action="store_true")
    add("cycle", cmd_cycle, "run exactly one engine cycle in the foreground")
    p = add("run", cmd_run, "run the bot in the foreground (used by start)")
    p.add_argument("--console", action="store_true", help="also log to the console")
    p = add("start", cmd_start, "launch the bot in the background")
    p.add_argument("--wait", type=int, default=45)
    p = add("stop", cmd_stop, "stop the bot; positions keep their stops unless --close-all")
    p.add_argument("--close-all", action="store_true", help="kill switch: also close every bot position")
    p = add("status", cmd_status, "bot health, risk state, positions, last decisions")
    p.add_argument("--live", action="store_true", help="also query the terminal for live positions")
    add("pause", cmd_pause, "stop opening new trades (positions still managed)")
    p = add("resume", cmd_resume, "allow new trades again")
    p.add_argument("--reset-halt", action="store_true", help="clear a drawdown halt (owner's decision)")
    p = add("veto", cmd_veto, "block entries in one symbol for some hours")
    p.add_argument("symbol")
    p.add_argument("--hours", type=float, default=4.0)
    p.add_argument("--reason", default="operator veto")
    p = add("unveto", cmd_unveto, "remove a veto")
    p.add_argument("symbol")
    p = add("close", cmd_close, "close bot positions")
    p.add_argument("--all", action="store_true")
    p.add_argument("--symbol")
    p.add_argument("--ticket", type=int)
    p = add("report", cmd_report, "performance from the trade journal")
    p.add_argument("--days", type=int)
    p = add("live", cmd_live, "show/enable/disable real-money trading")
    p.add_argument("--enable", action="store_true")
    p.add_argument("--disable", action="store_true")
    p.add_argument("--login", type=int)
    p.add_argument("--owner-confirmed", action="store_true")
    p.add_argument("--override-validation", action="store_true")
    p = add("backtest", cmd_backtest, "test the current settings on history (broker data, or --csv DIR)")
    p.add_argument("--csv", help="directory of <SYMBOL>.csv files (time,open,high,low,close)")
    p.add_argument("--bars", type=int, default=20000)
    p.add_argument("--cost-mult", type=float, default=1.0)
    p.add_argument("--utc-offset-hours", type=float, default=0.0)
    p.add_argument("--ignore-halt", action="store_true", help="keep simulating past the drawdown kill-switch")
    add("watchdog", cmd_watchdog, "restart the bot if it should be running but is not")
    p = add("autostart", cmd_autostart, "Windows: keep the bot alive across crashes and reboots")
    p.add_argument("--install", action="store_true")
    p.add_argument("--remove", action="store_true")
    p = add("selftest", cmd_selftest, "run the whole engine against a simulated broker (no MT5 needed)")
    p.add_argument("--hours", type=int, default=400)

    args = ap.parse_args()
    if args.home:
        os.environ["FXBOT_HOME"] = args.home
    try:
        args.fn(args)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
