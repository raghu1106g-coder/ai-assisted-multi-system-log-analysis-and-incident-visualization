#!/usr/bin/env python3
"""
Deterministic generator for the PS3 *SYNTHETIC PROTOTYPE* dataset.

Everything here is fictional. Log-family names, formats, event vocabularies,
identifiers and fault codes are PROTOTYPE ASSUMPTIONS, not the official
hackathon dataset. Re-running with the same seed reproduces byte-identical output.

Usage:  python3 tools/generate_dataset.py [output_root]
"""
import os, sys, io, csv, json, re, random, calendar, datetime as dt

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                       os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
rng = random.Random(20310512)

A, B, C = "NODE_A", "NODE_B", "NODE_C"
NODES = [A, B, C]
FAMS = ["operator", "planning", "guidance", "state", "fault_recovery"]
ABBR = {"operator": "OPR", "planning": "PLN", "guidance": "GDN", "state": "STA", "fault_recovery": "FLT"}
BASE = dt.datetime(2031, 5, 12, tzinfo=dt.timezone.utc)   # fictional date


# ----------------------------------------------------------------- time helpers
def ms(n):
    return dt.timedelta(milliseconds=int(round(n)))


def T(s, off_ms=0):
    hms, _, frac = s.partition(".")
    h, m, sec = (int(x) for x in hms.split(":"))
    t = BASE + dt.timedelta(hours=h, minutes=m, seconds=sec, milliseconds=int((frac + "000")[:3]) if frac else 0)
    return t + ms(off_ms) if off_ms else t


def _ms(t): return f"{t.microsecond // 1000:03d}"
def f_iso_ms(t): return t.strftime("%Y-%m-%dT%H:%M:%S.") + _ms(t) + "Z"
def f_plan(t): return t.strftime("%Y-%m-%d %H:%M:%S.") + _ms(t)
def f_epoch(t): return f"{calendar.timegm(t.utctimetuple())}.{_ms(t)}"
def f_compact(t): return t.strftime("%Y%m%dT%H%M%S.") + _ms(t) + "Z"
def f_iso_s(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------- event store
EVENTS = {(n, f): [] for n in NODES for f in FAMS}


def add(node, fam, t, etype, sev="INFO", comp="", text="", tag=None, **kv):
    if isinstance(t, str):
        t = T(t)
    e = {"node": node, "fam": fam, "ts": t, "etype": etype, "sev": sev, "comp": comp,
         "text": text, "tag": tag, "kv": kv}
    EVENTS[(node, fam)].append(e)
    return e


WINDOWS = [(T("09:41:00"), T("09:41:35")), (T("10:05:05"), T("10:05:55")), (T("09:25:05"), T("09:26:00"))]


def rtimes(n, lo="09:00:20", hi="10:29:40"):
    out, lo_t, hi_t = [], T(lo), T(hi)
    span = int((hi_t - lo_t).total_seconds() * 1000)
    while len(out) < n:
        t = lo_t + ms(rng.randrange(span))
        if any(a <= t <= b for a, b in WINDOWS):
            continue
        out.append(t)
    return sorted(out)


# ----------------------------------------------------------------- renderers (one syntax per family)
OPN = {"cmd": "cmd_id", "alert": "alert_id"}


def r_operator(e):
    kv = e["kv"]
    p = [f"[ts={f_iso_ms(e['ts'])}][node={e['node']}][sev={e['sev']}]", f"op={kv.get('op', 'OP-00')}", f"action={e['etype']}"]
    for k, v in kv.items():
        if k != "op":
            p.append(f"{OPN.get(k, k)}={v}")
    if e["comp"]:
        p.append(f"component={e['comp']}")
    p.append(f'msg="{e["text"]}"')
    return " ".join(p)


PL_COLS = ["ts", "node", "event", "plan_id", "msg_id", "peer", "cmd_ref", "ack_for", "resend_of", "component", "status", "detail"]


def r_planning(e):
    kv = e["kv"]
    row = [f_plan(e["ts"]), e["node"], e["etype"], kv.get("plan", ""), kv.get("msg", ""), kv.get("peer", ""),
           kv.get("cmd", ""), kv.get("ack_for", ""), kv.get("resend_of", ""), e["comp"], kv.get("status", ""), e["text"]]
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(row)
    return buf.getvalue()


def r_guidance(e):
    toks = [f_epoch(e["ts"]), e["node"], "GDN", f"evt={e['etype']}", f"sev={e['sev']}", f"comp={e['comp']}"]
    toks += [f"{k}={v}" for k, v in e["kv"].items()]
    toks.append("note=" + e["text"].replace(" ", "_"))
    return " ".join(toks)


def r_state(e):
    kv = e["kv"]
    return ";".join([f_compact(e["ts"]), e["node"], e["etype"], e["comp"], kv.get("frm", "-"), kv.get("to", "-"),
                     kv.get("trigger", "-"), str(kv["seq"]), e["text"]])


def r_fault(e):
    kv = e["kv"]
    return "|".join([f_iso_s(e["ts"]), e["node"], e["etype"], kv.get("code", "-"), kv.get("name", "-"), e["comp"],
                     e["sev"], kv.get("related", "-"), kv.get("dur", "-"), e["text"]])


RENDER = {"operator": r_operator, "planning": r_planning, "guidance": r_guidance, "state": r_state, "fault_recovery": r_fault}

CATEGORY = {
    "SESSION_START": "OPERATOR_ACTION", "STATUS_QUERY": "OPERATOR_ACTION", "VIEW_CHANGE": "OPERATOR_ACTION",
    "ADJUST_DISPLAY": "OPERATOR_ACTION", "MAINT_NOTE": "OPERATOR_ACTION", "ACK_ALERT": "OPERATOR_ACTION",
    "SUBMIT_COMMAND": "COMMAND",
    "PLAN_REQUEST": "PLANNING", "PLAN_COMPUTED": "PLANNING", "PLAN_REFRESH": "PLANNING",
    "MESSAGE_SENT": "MESSAGE", "MESSAGE_RECEIVED": "MESSAGE", "MESSAGE_ACK": "MESSAGE", "EXCHANGE_COMPLETE": "MESSAGE",
    "WAYPOINT_REACHED": "GUIDANCE", "GUIDANCE_STATUS": "GUIDANCE", "PROFILE_APPLY": "GUIDANCE", "GUIDANCE_NOMINAL": "GUIDANCE",
    "FILTER_REINIT": "GUIDANCE", "PLAN_HOLD": "GUIDANCE", "PLAN_RESUME": "GUIDANCE", "GUIDANCE_DEVIATION": "ANOMALY",
    "SETPOINT_SENT": "SETPOINT", "SETPOINT_RECEIVED": "SETPOINT", "SETPOINT_ACK": "SETPOINT",
    "SETPOINT_APPLIED": "SETPOINT", "SETPOINT_COMPLETE": "SETPOINT", "SETPOINT_REJECTED": "SETPOINT",
    "STATE_CHANGE": "STATE_CHANGE", "PHASE_CHANGE": "PHASE", "PEER_STATE": "PEER_STATE", "CONDITION_SAMPLE": "CONDITION",
    "FAULT_RAISED": "FAULT", "FAULT_CLEARED": "FAULT", "TRANSIENT_WARN": "FAULT", "PEER_FAULT_NOTICE": "FAULT",
    "FAULT_NOTICE_SENT": "FAULT", "RECOVERY_STARTED": "RECOVERY", "SELFTEST_PASS": "HEALTH",
}
ID_RE = re.compile(r"^(CMD|MSG|FLT|RCV|SP|PLN)-\d+$")
HINT_KEYS = ("code", "cmd", "msg", "ack_for", "resend_of", "sp", "plan", "related", "trigger", "ref", "alert")


def eff_sev(e):
    f = e["fam"]
    if f in ("operator", "guidance", "fault_recovery"):
        return e["sev"]
    if f == "planning":
        return "ERROR" if e["kv"].get("status") in ("FAILED", "TIMEOUT") else "INFO"
    return "WARN" if e["kv"].get("to") in ("DEGRADED", "TIMEOUT", "RETRY") else "INFO"


def entity_of(e):
    for k in ("code", "msg", "ack_for", "cmd", "sp", "plan", "wp", "alert"):
        v = e["kv"].get(k)
        if v and v != "-":
            return v
    return e["comp"] or "-"


def hint_of(e):
    for k in HINT_KEYS:
        v = e["kv"].get(k)
        if v and ID_RE.match(str(v)):
            return v
    return None


# ================================================================= BACKGROUND (normal activity)
PHASE_OF = [("09:01:30", "CLIMB"), ("09:20:00", "CRUISE"), ("10:12:00", "DESCENT"), ("10:24:00", "APPROACH")]
BAND = {"PREFLIGHT": ("L0", "S0"), "CLIMB": ("L2", "S2"), "CRUISE": ("L5", "S3"), "DESCENT": ("L3", "S2"), "APPROACH": ("L1", "S1")}


def phase_at(t):
    ph = "PREFLIGHT"
    for s, name in PHASE_OF:
        if t >= T(s):
            ph = name
    return ph


OPS = {A: "OP-07", B: "OP-03", C: "OP-05"}
COMPS = ["NAV_FILTER", "ROUTE_MGR", "PLAN_SYNC", "COMM_LINK", "SPEED_CTRL", "SENSOR_BUS"]


def bg_operator():
    add(A, "operator", "09:00:10.300", "SESSION_START", "INFO", "SESSION", "Operator session opened for simulated session SIM-S01",
        tag="bg_op_A_session", op=OPS[A], origin="ZZ-ALPHA", dest="ZZ-BRAVO")
    add(B, "operator", "09:00:12.800", "SESSION_START", "INFO", "SESSION", "Maintenance console session opened",
        tag="bg_op_B_session", op=OPS[B])
    add(C, "operator", "09:00:15.100", "SESSION_START", "INFO", "SESSION", "Monitor console session opened",
        tag="bg_op_C_session", op=OPS[C])
    for t, cmd, txt in [("09:09:14.500", "CMD-1001", "Operator confirmed route leg 2"),
                        ("09:47:22.300", "CMD-1012", "Operator confirmed route leg 5"),
                        ("10:14:08.900", "CMD-1033", "Operator confirmed descent briefing items")]:
        add(A, "operator", t, "SUBMIT_COMMAND", "INFO", "ROUTE_MGR", txt, op=OPS[A], cmd=cmd, attempt=1)
    add(B, "operator", "09:12:44.800", "STATUS_QUERY", "INFO", "NAV_FILTER", "Operator queried status of NAV_FILTER",
        tag="bg_op_B_query1", op=OPS[B])
    for node, n in [(A, 10), (B, 17), (C, 18)]:
        for t in rtimes(n):
            kind = rng.choice(["STATUS_QUERY", "STATUS_QUERY", "VIEW_CHANGE", "ADJUST_DISPLAY", "MAINT_NOTE"])
            if kind == "STATUS_QUERY":
                c = rng.choice(COMPS); txt = f"Operator queried status of {c}"
            elif kind == "VIEW_CHANGE":
                c = "DISPLAY_SVC"; txt = f"Operator switched display to page P{rng.randint(1, 6)}"
            elif kind == "ADJUST_DISPLAY":
                c = "DISPLAY_SVC"; txt = f"Operator changed display {rng.choice(['brightness', 'contrast', 'scale'])}"
            else:
                c = rng.choice(COMPS); txt = f"Operator logged maintenance note {rng.randint(100, 199)}"
            add(node, "operator", t, kind, "INFO", c, txt, op=OPS[node])


def exchange(src, dst, mid, t0, plan, pre=None, detail="periodic status plan sync"):
    tg = (lambda s: f"{pre}_{s}") if pre else (lambda s: None)
    ts = T(t0) + ms(rng.randint(0, 400))
    add(src, "planning", ts, "MESSAGE_SENT", "INFO", "PLAN_SYNC", detail, tag=tg("sent"), plan=plan, msg=mid, peer=dst, status="SENT")
    tr = ts + ms(rng.randint(250, 450))
    add(dst, "planning", tr, "MESSAGE_RECEIVED", "INFO", "PLAN_SYNC", detail, tag=tg("recv"), plan=plan, msg=mid, peer=src, status="RECEIVED")
    ta = tr + ms(rng.randint(150, 400))
    add(dst, "planning", ta, "MESSAGE_ACK", "INFO", "PLAN_SYNC", "acknowledged", tag=tg("ack"), plan=plan, peer=src, ack_for=mid, status="ACKED")
    tc = ta + ms(rng.randint(150, 300))
    add(src, "planning", tc, "EXCHANGE_COMPLETE", "INFO", "PLAN_SYNC", "exchange closed", tag=tg("done"), plan=plan, msg=mid, peer=dst, status="COMPLETE")


def bg_planning():
    for k in range(6):                      # periodic cache refresh on every node
        for node, off in [(A, 0), (B, 4), (C, 9)]:
            if node == C and k == 3:
                tag = "bg_pl_C_refresh3"
            else:
                tag = f"bg_pl_{node[-1]}_refresh{k}"
            t = T("09:02:00") + dt.timedelta(minutes=15 * k, seconds=off) + ms(rng.randint(0, 900))
            txt = ("initial route ZZ-ALPHA->ZZ-BRAVO loaded, 6 legs" if (node == A and k == 0)
                   else rng.choice(["periodic plan cache refresh", "refresh complete, no changes"]))
            add(node, "planning", t, "PLAN_REFRESH", "INFO", "PLAN_CACHE", txt, tag=tag, plan=f"PLN-{200 + k}", status="OK")
    exchange(A, B, "MSG-701", "09:05:20", "PLN-300", "bg_s1a")
    exchange(A, C, "MSG-702", "09:05:20", "PLN-300", "bg_s1b")
    exchange(A, B, "MSG-703", "09:15:40", "PLN-301", "bg_s2")           # sent record is corrupted later
    exchange(A, C, "MSG-704", "09:15:40", "PLN-301", "bg_s2c")
    exchange(A, B, "MSG-705", "09:52:10", "PLN-302", "bg_s4a")
    exchange(A, C, "MSG-706", "09:52:10", "PLN-302", "bg_s4b")
    exchange(A, B, "MSG-709", "10:20:40", "PLN-303", "bg_s6a")
    exchange(A, C, "MSG-710", "10:20:40", "PLN-303", "bg_s6b")
    exchange(B, C, "MSG-715", "09:58:30", "PLN-306", "bg_bc", "peer status report")
    exchange(C, A, "MSG-716", "10:15:15", "PLN-307", "bg_ca", "peer status report")


WPS = ["09:03:10", "09:07:40", "09:12:20", "09:16:50", "09:20:30", "09:25:50", "09:30:15", "09:34:40", "09:39:20",
       "09:41:08.500", "09:46:30", "09:51:00", "09:55:35", "10:00:10", "10:04:30", "10:09:20", "10:13:50", "10:18:25",
       "10:23:00", "10:27:40"]


def bg_guidance():
    for i, s in enumerate(WPS, 1):
        for node in NODES:
            if node == B and i == 12:
                continue                      # INTENTIONALLY MISSING background record (WP-012 on NODE_B)
            if i == 5:
                off = {A: 0, B: 210, C: 0}[node]          # A and C simultaneous to the millisecond
            elif i == 10:
                off = {A: 0, B: 120, C: 210}[node]
            else:
                off = {A: rng.randint(5, 90), B: rng.randint(120, 600), C: rng.randint(100, 900)}[node]
            add(node, "guidance", T(s, off), "WAYPOINT_REACHED", "INFO", "ROUTE_MGR", f"waypoint {i} reached",
                tag=f"bg_gd_{node[-1]}_wp{i:02d}", wp=f"WP-{i:03d}")
    for k in range(9):
        for node, off in [(A, 0), (B, 17), (C, 34)]:
            t = T("09:05:00") + dt.timedelta(minutes=10 * k, seconds=off) + ms(rng.randint(100, 900))
            add(node, "guidance", t, "GUIDANCE_STATUS", "INFO", "GUIDANCE_CORE", "periodic guidance status",
                tag=f"bg_gd_{node[-1]}_hb{k + 1}", mode="NOMINAL", hb=k + 1)


def bg_state():
    phases = [("09:01:30", "PREFLIGHT", "CLIMB"), ("09:20:00", "CLIMB", "CRUISE"),
              ("10:12:00", "CRUISE", "DESCENT"), ("10:24:00", "DESCENT", "APPROACH")]
    for i, (s, f, t_) in enumerate(phases, 1):
        for node in NODES:
            if i == 2 and node in (A, C):
                off = 0                        # simultaneous phase change on A and C
            else:
                off = {A: rng.randint(10, 400), B: 340 + rng.randint(0, 200), C: rng.randint(10, 400)}[node]
            add(node, "state", T(s, off), "PHASE_CHANGE", "INFO", "FLIGHT_PHASE", f"phase transition {f} to {t_}",
                tag=f"bg_sta_{node[-1]}_ph{i}", frm=f, to=t_)
    for k in range(9):
        for node, off in [(A, 0), (B, 1), (C, 2)]:
            t = T("09:00:30") + dt.timedelta(minutes=10 * k, seconds=off) + ms(rng.randint(0, 900))
            ph = phase_at(t); alt, spd = BAND[ph]
            add(node, "state", t, "CONDITION_SAMPLE", "INFO", "NAV_ENV",
                f"alt_band={alt} spd_band={spd} fuel_state=OK link=UP phase={ph}", tag=f"bg_sta_{node[-1]}_cond{k + 1}")
    for node, pairs in [(B, [("09:11:07.400", "09:11:08.900"), ("09:58:45.100", "09:58:46.300")]),
                        (C, [("09:19:12.600", "09:19:13.900"), ("10:08:30.000", "10:08:31.200")])]:
        for j, (a, b) in enumerate(pairs, 1):
            add(node, "state", a, "STATE_CHANGE", "INFO", "SENSOR_BUS", "bus retry started", tag=f"bg_sta_{node[-1]}_sens{j}a", frm="NOMINAL", to="RETRY", trigger="-")
            add(node, "state", b, "STATE_CHANGE", "INFO", "SENSOR_BUS", "bus retry recovered", tag=f"bg_sta_{node[-1]}_sens{j}b", frm="RETRY", to="NOMINAL", trigger="-")


def bg_fault():
    comp = {A: "ROUTE_MGR", B: "NAV_FILTER", C: "PLAN_SYNC"}
    for k in range(15):
        for node, off in [(A, 0), (B, 7), (C, 13)]:
            t = T("09:00:40") + dt.timedelta(minutes=6 * k, seconds=off)
            add(node, "fault_recovery", t, "SELFTEST_PASS", "INFO", comp[node], f"self test passed cycle {k + 1}",
                tag=f"bg_flt_{node[-1]}_st{k + 1}", code="ST-001", name="SELFTEST")
    for t in ("09:10:33", "09:48:09"):
        add(A, "fault_recovery", t, "TRANSIENT_WARN", "WARN", "COMM_LINK", "link jitter above threshold, self-cleared",
            code="FLT-0901", name="COMM_LINK_JITTER", dur="1")
    for t in ("09:37:21", "10:15:44"):
        add(B, "fault_recovery", t, "TRANSIENT_WARN", "WARN", "SENSOR_BUS", "bus retry succeeded",
            code="FLT-0420", name="SENSOR_BUS_RETRY", dur="1")


# ================================================================= INCIDENTS
def inc1():
    # ---- operator
    add(A, "operator", "09:41:02.120", "SUBMIT_COMMAND", "INFO", "ROUTE_MGR", "Operator requested alternate route profile ALT-2",
        tag="i1_op_submit1", op=OPS[A], cmd="CMD-1042", attempt=1)
    add(A, "operator", "09:41:03.900", "SUBMIT_COMMAND", "INFO", "ROUTE_MGR", "Operator resubmitted route profile request (no feedback shown)",
        tag="i1_op_submit2", op=OPS[A], cmd="CMD-1042", attempt=2)
    add(A, "operator", "09:41:04.500", "VIEW_CHANGE", "INFO", "DISPLAY_SVC", "Operator opened fault panel",
        tag="i1_op_A_panel", op=OPS[A])                                  # corrupted later (missing timestamp)
    add(A, "operator", "09:41:30.400", "ACK_ALERT", "INFO", "NAV_FILTER", "Operator acknowledged alert FLT-2207",
        tag="i1_op_ack_alert", op=OPS[A], alert="FLT-2207")
    add(B, "operator", "09:41:12.500", "STATUS_QUERY", "INFO", "NAV_FILTER", "Operator queried status of NAV_FILTER",
        tag="i1_op_B_query", op=OPS[B])
    add(C, "operator", "09:41:08.000", "ADJUST_DISPLAY", "INFO", "DISPLAY_SVC", "Operator changed display brightness",
        tag="u1_op_C_display", op=OPS[C])
    # ---- planning
    add(A, "planning", "09:41:02.600", "PLAN_REQUEST", "INFO", "ROUTE_MGR", "plan request for alternate profile ALT-2",
        tag="i1_pl_req", plan="PLN-310", cmd="CMD-1042", status="REQUESTED")
    add(A, "planning", "09:41:05.900", "PLAN_COMPUTED", "INFO", "ROUTE_MGR", "6 legs computed, 1 constraint relaxed",
        tag="i1_pl_comp", plan="PLN-310", cmd="CMD-1042", status="OK")
    add(A, "planning", "09:41:06.350", "MESSAGE_SENT", "INFO", "PLAN_SYNC", "plan PLN-310 distributed to peer",
        tag="i1_msg771_sent", plan="PLN-310", msg="MSG-771", peer=B, status="SENT")
    add(A, "planning", "09:41:06.360", "MESSAGE_SENT", "INFO", "PLAN_SYNC", "plan PLN-310 distributed to peer",
        tag="i1_msg772_sent", plan="PLN-310", msg="MSG-772", peer=C, status="SENT")
    add(B, "planning", "09:41:06.700", "MESSAGE_RECEIVED", "INFO", "PLAN_SYNC", "plan PLN-310 received",
        tag="i1_msg771_recv", plan="PLN-310", msg="MSG-771", peer=A, status="RECEIVED")
    add(C, "planning", "09:41:06.710", "MESSAGE_RECEIVED", "INFO", "PLAN_SYNC", "plan PLN-310 received",
        tag="i1_msg772_recv", plan="PLN-310", msg="MSG-772", peer=A, status="RECEIVED")
    add(B, "planning", "09:41:06.980", "MESSAGE_ACK", "INFO", "PLAN_SYNC", "acknowledged",
        tag="i1_msg771_ack", plan="PLN-310", peer=A, ack_for="MSG-771", status="ACKED")
    add(A, "planning", "09:41:07.600", "EXCHANGE_COMPLETE", "INFO", "PLAN_SYNC", "exchange closed",
        tag="i1_msg771_done", plan="PLN-310", msg="MSG-771", peer=B, status="COMPLETE")
    # (no MESSAGE_ACK / EXCHANGE_COMPLETE for MSG-772 -> intentionally absent)
    add(A, "planning", "09:41:25.100", "MESSAGE_SENT", "INFO", "PLAN_SYNC", "plan PLN-310 resent after peer notice",
        tag="i1_msg779_sent", plan="PLN-310", msg="MSG-779", peer=C, resend_of="MSG-772", status="SENT")
    add(C, "planning", "09:41:25.500", "MESSAGE_RECEIVED", "INFO", "PLAN_SYNC", "plan PLN-310 received (resend)",
        tag="i1_msg779_recv", plan="PLN-310", msg="MSG-779", peer=A, resend_of="MSG-772", status="RECEIVED")
    add(C, "planning", "09:41:25.800", "MESSAGE_ACK", "INFO", "PLAN_SYNC", "acknowledged",
        tag="i1_msg779_ack", plan="PLN-310", peer=A, ack_for="MSG-779", status="ACKED")
    add(A, "planning", "09:41:26.100", "EXCHANGE_COMPLETE", "INFO", "PLAN_SYNC", "exchange closed",
        tag="i1_msg779_done", plan="PLN-310", msg="MSG-779", peer=C, status="COMPLETE")
    # ---- guidance
    add(B, "guidance", "09:41:07.250", "PROFILE_APPLY", "INFO", "NAV_FILTER", "profile applied from received plan", tag="i1_g_B_apply", plan="PLN-310")
    add(C, "guidance", "09:41:07.250", "PROFILE_APPLY", "INFO", "NAV_FILTER", "profile applied from received plan", tag="i1_g_C_apply", plan="PLN-310")
    add(B, "guidance", "09:41:08.300", "GUIDANCE_DEVIATION", "WARN", "NAV_FILTER", "cross track error above soft limit", tag="i1_g_B_dev1", xte="0.82")
    add(B, "guidance", "09:41:08.900", "GUIDANCE_DEVIATION", "WARN", "NAV_FILTER", "cross track error above soft limit", tag="i1_g_B_dev2", xte="1.35")
    add(B, "guidance", "09:41:09.500", "GUIDANCE_DEVIATION", "WARN", "NAV_FILTER", "cross track error above soft limit", tag="i1_g_B_dev3", xte="2.10")
    add(B, "guidance", "09:41:22.400", "FILTER_REINIT", "INFO", "NAV_FILTER", "filter reinitialised", tag="i1_g_B_reinit", ref="RCV-55")
    add(B, "guidance", "09:41:28.900", "GUIDANCE_NOMINAL", "INFO", "NAV_FILTER", "tracking restored", tag="i1_g_B_stable")
    add(C, "guidance", "09:41:16.500", "PLAN_HOLD", "WARN", "PLAN_SYNC", "holding previous plan", tag="i1_g_C_hold")
    add(C, "guidance", "09:41:26.800", "PLAN_RESUME", "INFO", "PLAN_SYNC", "resuming with resent plan", tag="i1_g_C_resume", plan="PLN-310", ref="MSG-779")
    # ---- state
    add(A, "state", "09:41:02.480", "STATE_CHANGE", "INFO", "ROUTE_MGR", "replanning started", tag="i1_s_A_replan", frm="IDLE", to="REPLANNING", trigger="CMD-1042")
    add(A, "state", "09:41:07.900", "STATE_CHANGE", "INFO", "ROUTE_MGR", "new plan active", tag="i1_s_A_active", frm="REPLANNING", to="ACTIVE", trigger="PLN-310")
    add(A, "state", "09:41:10.100", "PEER_STATE", "INFO", "PEER_NODE_B", "peer reported degraded", tag="i1_s_A_peerB_deg", frm="NOMINAL", to="DEGRADED", trigger="MSG-775")
    add(A, "state", "09:41:17.200", "PEER_STATE", "INFO", "PEER_NODE_C", "peer reported degraded", tag="i1_s_A_peerC_deg", frm="NOMINAL", to="DEGRADED", trigger="MSG-776")
    add(A, "state", "09:41:27.400", "PEER_STATE", "INFO", "PEER_NODE_C", "peer back to nominal", tag="i1_s_A_peerC_ok", frm="DEGRADED", to="NOMINAL", trigger="-")
    add(A, "state", "09:41:29.200", "PEER_STATE", "INFO", "PEER_NODE_B", "peer back to nominal", tag="i1_s_A_peerB_ok", frm="DEGRADED", to="NOMINAL", trigger="-")
    add(B, "state", "09:41:08.900", "STATE_CHANGE", "INFO", "NAV_FILTER", "filter degraded", tag="i1_s_B_deg", frm="NOMINAL", to="DEGRADED", trigger="-")
    add(B, "state", "09:41:21.200", "STATE_CHANGE", "INFO", "NAV_FILTER", "filter recovering", tag="i1_s_B_rec", frm="DEGRADED", to="RECOVERING", trigger="RCV-55")
    add(B, "state", "09:41:28.600", "STATE_CHANGE", "INFO", "NAV_FILTER", "filter nominal", tag="i1_s_B_nom", frm="RECOVERING", to="NOMINAL", trigger="RCV-55")
    add(C, "state", "09:41:16.100", "STATE_CHANGE", "INFO", "PLAN_SYNC", "sync timed out", tag="i1_s_C_stale", frm="SYNCED", to="TIMEOUT", trigger="MSG-772")
    add(C, "state", "09:41:26.300", "STATE_CHANGE", "INFO", "PLAN_SYNC", "sync restored", tag="i1_s_C_synced", frm="TIMEOUT", to="SYNCED", trigger="MSG-779")
    # ---- fault / recovery (second resolution)
    nf = dict(code="FLT-2207", name="NAV_FILTER_DIVERGENCE")
    add(B, "fault_recovery", "09:41:09", "FAULT_RAISED", "ERROR", "NAV_FILTER", "residual above divergence limit", tag="i1_f_B_raise", **nf)
    add(B, "fault_recovery", "09:41:09", "FAULT_NOTICE_SENT", "INFO", "NAV_FILTER", "fault notice sent to NODE_A", tag="i1_f_B_notice", related="MSG-775", **nf)
    add(A, "fault_recovery", "09:41:10", "PEER_FAULT_NOTICE", "WARN", "PEER_NODE_B", "fault notice received from NODE_B", tag="i1_f_A_notice_B", related="MSG-775", **nf)
    add(A, "fault_recovery", "09:41:11", "TRANSIENT_WARN", "WARN", "COMM_LINK", "link jitter above threshold, self-cleared",
        tag="u1_f_A_jitter", code="FLT-0901", name="COMM_LINK_JITTER", dur="1")
    sf = dict(code="FLT-2210", name="PLAN_SYNC_TIMEOUT")
    add(C, "fault_recovery", "09:41:16", "FAULT_RAISED", "ERROR", "PLAN_SYNC", "sync timer expired (10s) for MSG-772", tag="i1_f_C_timeout1", related="MSG-772", **sf)
    add(C, "fault_recovery", "09:41:17", "FAULT_NOTICE_SENT", "INFO", "PLAN_SYNC", "fault notice sent to NODE_A", tag="i1_f_C_notice", related="MSG-776", **sf)
    add(A, "fault_recovery", "09:41:18", "PEER_FAULT_NOTICE", "WARN", "PEER_NODE_C", "fault notice received from NODE_C", tag="i1_f_A_notice_C", related="MSG-776", **sf)
    add(C, "fault_recovery", "09:41:19", "FAULT_RAISED", "ERROR", "PLAN_SYNC", "sync timer expired again (repeat 2) for MSG-772", tag="i1_f_C_timeout2", related="MSG-772", **sf)
    add(B, "fault_recovery", "09:41:21", "RECOVERY_STARTED", "INFO", "NAV_FILTER", "filter reinit scheduled", tag="i1_f_B_rcv", code="RCV-55", name="FILTER_REINIT", related="FLT-2207")
    add(C, "fault_recovery", "09:41:22", "FAULT_RAISED", "ERROR", "PLAN_SYNC", "sync timer expired again (repeat 3) for MSG-772", tag="i1_f_C_timeout3", related="MSG-772", **sf)  # corrupted later
    add(C, "fault_recovery", "09:41:24", "RECOVERY_STARTED", "INFO", "PLAN_SYNC", "request plan resend", tag="i1_f_C_rcv", code="RCV-56", name="REQUEST_PLAN_RESEND", related="FLT-2210")
    add(C, "fault_recovery", "09:41:27", "FAULT_CLEARED", "INFO", "PLAN_SYNC", "sync restored", tag="i1_f_C_clear", related="RCV-56", dur="11", **sf)
    add(B, "fault_recovery", "09:41:29", "FAULT_CLEARED", "INFO", "NAV_FILTER", "filter divergence cleared", tag="i1_f_B_clear", related="RCV-55", dur="20", **nf)


def inc2():
    add(A, "operator", "10:05:08.300", "SUBMIT_COMMAND", "INFO", "SPEED_CTRL", "Operator lowered speed limit by 12 percent", tag="i2_op_cmd", op=OPS[A], cmd="CMD-1018", attempt=1)
    add(A, "operator", "10:05:16.200", "STATUS_QUERY", "INFO", "SPEED_CTRL", "Operator queried status of SPEED_CTRL", tag="i2_op_A_query", op=OPS[A])
    add(B, "operator", "10:05:20.400", "MAINT_NOTE", "INFO", "SENSOR_BUS", "Operator logged maintenance note 142", tag="u2_op_B_note", op=OPS[B])
    add(A, "state", "10:05:08.700", "STATE_CHANGE", "INFO", "SPEED_CTRL", "speed adjustment started", tag="i2_s_A", frm="STABLE", to="ADJUSTING", trigger="CMD-1018")
    add(A, "guidance", "10:05:09.200", "SETPOINT_SENT", "INFO", "SPEED_CTRL", "setpoint sent to peer", tag="i2_g_A_sent", cmd="CMD-1018", sp="SP-044", peer=C)
    add(C, "guidance", "10:05:09.450", "SETPOINT_RECEIVED", "INFO", "SPEED_CTRL", "setpoint received", tag="i2_g_C_recv", cmd="CMD-1018", sp="SP-044", peer=A)
    add(C, "state", "10:05:09.800", "STATE_CHANGE", "INFO", "SPEED_CTRL", "speed adjustment started", tag="i2_s_C", frm="STABLE", to="ADJUSTING", trigger="SP-044")
    add(C, "fault_recovery", "10:05:11", "FAULT_RAISED", "ERROR", "SPEED_CTRL", "setpoint outside actuator range", tag="i2_f_C_raise", code="FLT-1304", name="SETPOINT_OUT_OF_RANGE", related="SP-044")
    add(A, "fault_recovery", "10:05:11", "TRANSIENT_WARN", "WARN", "COMM_LINK", "link jitter above threshold, self-cleared", tag="u2_f_A_jitter", code="FLT-0901", name="COMM_LINK_JITTER", dur="1")
    add(C, "fault_recovery", "10:05:12", "RECOVERY_STARTED", "INFO", "SPEED_CTRL", "reject setpoint and revert", tag="i2_f_C_rcv", code="RCV-61", name="REJECT_SETPOINT", related="FLT-1304")
    add(C, "state", "10:05:12.600", "STATE_CHANGE", "INFO", "SPEED_CTRL", "reverted to previous setpoint", tag="i2_s_C_rev", frm="ADJUSTING", to="STABLE", trigger="RCV-61")
    add(C, "guidance", "10:05:12.800", "SETPOINT_REJECTED", "WARN", "SPEED_CTRL", "setpoint rejected", tag="i2_g_C_reject", cmd="CMD-1018", sp="SP-044", ref="FLT-1304")
    add(C, "fault_recovery", "10:05:13", "FAULT_CLEARED", "INFO", "SPEED_CTRL", "setpoint rejected and reverted", tag="i2_f_C_clear", code="FLT-1304", name="SETPOINT_OUT_OF_RANGE", related="RCV-61", dur="2")
    # intentionally absent: C SETPOINT_ACK / SETPOINT_APPLIED for SP-044; A SPEED_CTRL ADJUSTING->STABLE


def inc3():
    add(A, "operator", "09:25:10.200", "SUBMIT_COMMAND", "INFO", "ALT_PROFILE", "Operator requested routine altitude profile step", tag="i3_op_cmd", op=OPS[A], cmd="CMD-1030", attempt=1)
    add(B, "operator", "09:25:34.600", "STATUS_QUERY", "INFO", "PLAN_SYNC", "Operator queried status of PLAN_SYNC", tag="u3_op_B_query", op=OPS[B])
    add(A, "state", "09:25:10.550", "STATE_CHANGE", "INFO", "ALT_PROFILE", "altitude step started", tag="i3_s_A_step", frm="LEVEL", to="STEPPING", trigger="CMD-1030")
    add(A, "guidance", "09:25:11.000", "SETPOINT_SENT", "INFO", "ALT_PROFILE", "setpoint sent to peer", tag="i3_g_A_sent", cmd="CMD-1030", sp="SP-039", peer=C)
    add(C, "guidance", "09:25:11.240", "SETPOINT_RECEIVED", "INFO", "ALT_PROFILE", "setpoint received", tag="i3_g_C_recv", cmd="CMD-1030", sp="SP-039", peer=A)
    add(C, "guidance", "09:25:11.500", "SETPOINT_ACK", "INFO", "ALT_PROFILE", "setpoint acknowledged", tag="i3_g_C_ack", ack_for="SP-039", peer=A)
    add(C, "guidance", "09:25:12.300", "SETPOINT_APPLIED", "INFO", "ALT_PROFILE", "setpoint applied", tag="i3_g_C_applied", sp="SP-039")
    add(C, "state", "09:25:12.350", "STATE_CHANGE", "INFO", "ALT_PROFILE", "altitude step started", tag="i3_s_C_step", frm="LEVEL", to="STEPPING", trigger="SP-039")
    add(A, "guidance", "09:25:12.600", "SETPOINT_COMPLETE", "INFO", "ALT_PROFILE", "setpoint cycle complete", tag="i3_g_A_done", cmd="CMD-1030", sp="SP-039")
    exchange(A, B, "MSG-740", "09:25:30", "PLN-308", "i3_msg740")
    exchange(A, C, "MSG-741", "09:25:30", "PLN-308", "i3_msg741")
    add(A, "state", "09:25:40.300", "STATE_CHANGE", "INFO", "ALT_PROFILE", "altitude step finished", tag="i3_s_A_end", frm="STEPPING", to="LEVEL", trigger="CMD-1030")
    add(C, "state", "09:25:40.350", "STATE_CHANGE", "INFO", "ALT_PROFILE", "altitude step finished", tag="i3_s_C_end", frm="STEPPING", to="LEVEL", trigger="SP-039")
    add(C, "fault_recovery", "09:25:55", "TRANSIENT_WARN", "WARN", "SENSOR_BUS", "bus retry succeeded", tag="u3_f_C_warn", code="FLT-0420", name="SENSOR_BUS_RETRY", dur="1")


# ================================================================= CORRUPTION + ORDERING
def _c_op_nots(raw): return re.sub(r"\[ts=[^\]]*\]", "", raw)
def _c_op_incomplete(raw): return raw[:raw.index('msg="') + 18].replace(" component=", " cmd_id component=")
def _c_pl_short(raw): return ",".join(raw.split(",")[:4])
def _c_pl_nots(raw): return "," + raw.split(",", 1)[1]
def _c_gd_ts(raw): return raw[:4] + "X" + raw[5:]
def _c_gd_trunc(raw): return raw[:raw.index(" evt=") + 14]
def _c_st_sep(raw): return raw.replace(";", ",")
def _c_st_short(raw): return ";".join(raw.split(";")[:5])
def _c_fl_sep(raw): return raw.replace("|", ";")
def _c_fl_corrupt(raw): return raw.replace("FAULT_RAISED", "FAUL\ufffd_RA\ufffdSED")


CORRUPT = {   # tag -> (function, reason, incident)
    "i1_op_A_panel": (_c_op_nots, "missing_timestamp", "INC-001"),
    "bg_op_B_query1": (_c_op_incomplete, "incomplete_key_value_pair_and_unterminated_quote", None),
    "bg_s2_sent": (_c_pl_short, "incomplete_fields", None),
    "bg_pl_C_refresh3": (_c_pl_nots, "missing_timestamp", None),
    "bg_gd_B_hb5": (_c_gd_ts, "corrupted_timestamp_token", None),
    "bg_gd_C_wp18": (_c_gd_trunc, "truncated_record", None),
    "bg_sta_A_cond6": (_c_st_sep, "invalid_separator", None),
    "bg_sta_C_sens2a": (_c_st_short, "incomplete_fields", None),
    "bg_flt_B_st5": (_c_fl_sep, "invalid_separator", None),
    "i1_f_C_timeout3": (_c_fl_corrupt, "corrupted_event_name", "INC-001"),
}

MOVES = [  # (node, family, tag_to_move, 'before'|'after', anchor_tag)  -> out-of-order file positions
    (A, "planning", "i1_pl_comp", "after", "i1_msg771_sent"),
    (B, "guidance", "i1_g_B_dev2", "after", "i1_g_B_dev3"),
    (C, "state", "i1_s_C_stale", "after", "i1_s_C_synced"),
    (A, "fault_recovery", "u1_f_A_jitter", "before", "i1_f_A_notice_B"),
]

# ================================================================= BUILD
bg_operator(); bg_planning(); bg_guidance(); bg_state(); bg_fault()
inc1(); inc2(); inc3()

REG, LOST, FILES = {}, {}, {}
for (node, fam), evs in EVENTS.items():
    evs.sort(key=lambda e: e["ts"])                 # stable
    if fam == "state":
        for i, e in enumerate(evs):
            e["kv"]["seq"] = 100 + i                 # per-node monotonic seq (gaps reveal lost records)
    for (n, f, tag, how, anchor) in MOVES:
        if (n, f) != (node, fam):
            continue
        e = next(x for x in evs if x["tag"] == tag)
        evs.remove(e)
        j = next(i for i, x in enumerate(evs) if x["tag"] == anchor)
        evs.insert(j + 1 if how == "after" else j, e)
    rel_path = f"data/synthetic/{'node_' + node[-1]}/{fam}.log"
    lines, meta = [], {"path": rel_path, "node": node, "log_family": fam, "valid": [], "malformed": [], "header": 0}
    if fam == "planning":
        lines.append(",".join(PL_COLS)); meta["header"] = 1
    for e in evs:
        raw = RENDER[fam](e)
        lines.append(raw)
        lineno = len(lines)
        if e["tag"] in CORRUPT:
            fn, reason, inc = CORRUPT[e["tag"]]
            lines[-1] = fn(raw)
            LOST[e["tag"]] = {"file": rel_path, "line": lineno, "raw": lines[-1], "reason": reason, "incident": inc,
                              "orig": e}
            meta["malformed"].append(lineno)
        else:
            e["file"], e["line"] = rel_path, lineno
            e["event_id"] = f"EVT-{node[-1]}-{ABBR[fam]}-{lineno:04d}"
            e["raw"] = raw
            meta["valid"].append(e)
            if e["tag"]:
                REG[e["tag"]] = e
    meta["lines"] = lines
    FILES[(node, fam)] = meta

# ---- write raw files
for (node, fam), meta in FILES.items():
    p = os.path.join(ROOT, meta["path"])
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(meta["lines"]) + "\n")
with open(os.path.join(ROOT, "data/synthetic/SYNTHETIC_NOTICE.txt"), "w") as fh:
    fh.write("SYNTHETIC PROTOTYPE DATA - FICTIONAL\n"
             "All content under data/synthetic/ was generated for hackathon prototyping of Problem Statement 3.\n"
             "It is NOT the official dataset, NOT real flight-management data, and the log-family names,\n"
             "formats, event types, identifiers and fault codes are prototype assumptions only.\n")


# ================================================================= NORMALIZATION REFERENCE
def normalize(e):
    attrs = {k: str(v) for k, v in e["kv"].items()}
    return {
        "event_id": e["event_id"], "timestamp": f_iso_ms(e["ts"]), "node": e["node"], "log_family": e["fam"],
        "event_type": e["etype"], "severity": eff_sev(e), "component": e["comp"] or None, "entity": entity_of(e),
        "incident_hint": hint_of(e), "message": e["text"],
        "source_file": e["file"], "source_line": e["line"], "raw_record": e["raw"],
        "category": CATEGORY[e["etype"]],                                   # optional prototype extension
        "timestamp_precision": "s" if e["fam"] == "fault_recovery" else "ms",  # optional prototype extension
        "attributes": attrs,                                                # optional prototype extension
    }


ALL_VALID = [e for m in FILES.values() for e in m["valid"]]
ALL_VALID.sort(key=lambda e: (e["ts"], e["node"], e["fam"], e["line"]))
NORM = [normalize(e) for e in ALL_VALID]


def dump(path, obj):
    p = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


NOTICE = ("SYNTHETIC PROTOTYPE - not the official PS3 dataset or schema. "
          "Field names are a suggestion; replace when the official dataset/schema is released.")
EX_TAGS = ["i1_op_submit1", "i1_msg771_sent", "i1_msg771_recv", "i1_g_B_dev1", "i1_g_B_apply", "i1_s_A_replan",
           "bg_sta_A_ph2", "i1_f_B_raise", "i1_f_C_timeout1", "i1_f_B_rcv"]
dump("normalized_event_examples.json", {
    "_notice": NOTICE,
    "_parsing_rules": {
        "timestamp": "normalise every family to ISO-8601 UTC with milliseconds; fault_recovery is second-resolution (timestamp_precision='s')",
        "event_id": "EVT-<node letter>-<family code OPR|PLN|GDN|STA|FLT>-<4-digit source line>",
        "severity": "taken from the record when present (operator, guidance, fault_recovery); derived for planning (status FAILED/TIMEOUT=ERROR) and state (to-state DEGRADED/TIMEOUT/RETRY=WARN)",
        "incident_hint": "first correlation key found in the record (CMD/MSG/FLT/RCV/SP/PLN id). It is derived from the raw record only and is NOT the ground-truth incident id.",
        "entity": "primary identifier of the record (code > msg > ack_for > cmd > sp > plan > wp > alert > component)"},
    "examples": [normalize(REG[t]) for t in EX_TAGS]})
dump("reference/parser_expected_events.json", {"_notice": NOTICE + " This is an answer key for testing YOUR parser; do not feed it to the correlation engine.",
                                               "count": len(NORM), "events": NORM})


# ================================================================= GROUND TRUTH
def eid(tag): return REG[tag]["event_id"]
def ref(tag): return f"{REG[tag]['file']}:{REG[tag]['line']}"
def lab(tag): return {"event_id": eid(tag), "label": tag, "source_file": REG[tag]["file"], "source_line": REG[tag]["line"],
                      "timestamp": f_iso_ms(REG[tag]["ts"])}
def labs(tags): return [lab(t) for t in tags]


RELS = []
def rel(src, dst, typ, strength, reason, inc, key=None, label=None, seqpat=None):
    RELS.append(dict(src=src, dst=dst, typ=typ, strength=strength, reason=reason, inc=inc, key=key,
                     label=label or {"strong": "STRONG_SUPPORTED", "medium": "POSSIBLE", "weak": "POSSIBLE"}[strength], seqpat=seqpat))
def X(src, dst, key, inc, reason=None, typ="EXPLICIT_ID", note=""):
    rel(src, dst, typ, "strong", reason or f"Both records carry identifier {key}. {note}".strip(), inc, key)
def FLOW(src, dst, key, inc, note=""):
    rel(src, dst, "MESSAGE_FLOW", "strong", f"Sender and receiver both carry {key} (send->receive across nodes). {note}".strip(), inc, key)
def SEQ(src, dst, key, inc, pat, why):
    rel(src, dst, "SEQUENCE", "strong", why, inc, key, seqpat=pat)
def RCV(src, dst, key, inc, why=None):
    rel(src, dst, "RECOVERY", "strong", why or f"Recovery/clear record references {key}.", inc, key)

P4 = "SEND->RECV->ACK->COMPLETE"
I1 = "INC-001"
# --- INC-001 : commands / planning
X("i1_op_submit1", "i1_pl_req", "CMD-1042", I1, note="Operator command and plan request share the command id.")
X("i1_op_submit1", "i1_s_A_replan", "CMD-1042", I1, note="State trigger references the command.")
X("i1_op_submit1", "i1_op_submit2", "CMD-1042", I1, note="attempt=1 and attempt=2: repeated submission of the same command.")
X("i1_pl_req", "i1_pl_comp", "PLN-310", I1)
X("i1_pl_comp", "i1_s_A_active", "PLN-310", I1)
X("i1_pl_comp", "i1_msg771_sent", "PLN-310", I1); X("i1_pl_comp", "i1_msg772_sent", "PLN-310", I1)
X("i1_pl_comp", "i1_g_B_apply", "PLN-310", I1); X("i1_pl_comp", "i1_g_C_apply", "PLN-310", I1)
X("i1_g_B_apply", "i1_g_C_apply", "PLN-310", I1, note="Same plan id and identical timestamp (simultaneous) on two nodes.")
# --- INC-001 : message flows
FLOW("i1_msg771_sent", "i1_msg771_recv", "MSG-771", I1); FLOW("i1_msg772_sent", "i1_msg772_recv", "MSG-772", I1)
SEQ("i1_msg771_recv", "i1_msg771_ack", "MSG-771", I1, P4, "ACK_FOR=MSG-771 follows MESSAGE_RECEIVED MSG-771.")
SEQ("i1_msg771_ack", "i1_msg771_done", "MSG-771", I1, P4, "EXCHANGE_COMPLETE MSG-771 follows the ACK.")
FLOW("i1_msg779_sent", "i1_msg779_recv", "MSG-779", I1)
SEQ("i1_msg779_recv", "i1_msg779_ack", "MSG-779", I1, P4, "ACK_FOR=MSG-779 follows receipt.")
SEQ("i1_msg779_ack", "i1_msg779_done", "MSG-779", I1, P4, "Resent exchange completes.")
X("i1_msg779_sent", "i1_msg772_sent", "MSG-772", I1, note="MSG-779 carries resend_of=MSG-772.")
X("i1_g_C_resume", "i1_msg779_recv", "MSG-779", I1); X("i1_s_C_synced", "i1_msg779_recv", "MSG-779", I1)
# --- INC-001 : C-side fault chain
X("i1_msg772_sent", "i1_f_C_timeout1", "MSG-772", I1, note="Fault record names MSG-772 as the subject of the timeout. It states a timeout; it does not say why no ACK arrived.")
X("i1_s_C_stale", "i1_f_C_timeout1", "MSG-772", I1)
X("i1_f_C_timeout1", "i1_f_C_timeout2", "FLT-2210", I1, note="Repeated raise of the same fault (repeat 2).")
X("i1_f_C_timeout1", "i1_f_C_notice", "FLT-2210", I1)
FLOW("i1_f_C_notice", "i1_f_A_notice_C", "MSG-776", I1)
X("i1_f_A_notice_C", "i1_s_A_peerC_deg", "MSG-776", I1)
RCV("i1_f_C_timeout1", "i1_f_C_rcv", "FLT-2210", I1)
RCV("i1_f_C_rcv", "i1_f_C_clear", "RCV-56", I1)
RCV("i1_f_C_timeout1", "i1_f_C_clear", "FLT-2210", I1)
rel("i1_f_C_timeout1", "i1_f_C_clear", "RECOVERY", "strong", "Same fault code FLT-2210; duration_s=11 matches 09:41:16 -> 09:41:27.", I1, "FLT-2210")
rel("i1_f_A_notice_C", "i1_msg779_sent", "TEMPORAL", "medium", "A resent the plan ~7s after receiving the timeout notice. No record links the resend to the notice (possible relationship).", I1, label="POSSIBLE")
rel("i1_f_C_rcv", "i1_msg779_sent", "TEMPORAL", "medium", "C 'request plan resend' precedes A's resend by ~1.1s; no explicit reference between them (possible relationship).", I1, label="POSSIBLE")
rel("i1_g_C_hold", "i1_f_C_timeout1", "SHARED_COMPONENT", "medium", "Both concern PLAN_SYNC on NODE_C within 0.5s; guidance record has no explicit id.", I1)
rel("i1_s_C_synced", "i1_f_C_clear", "SHARED_COMPONENT", "medium", "PLAN_SYNC returned to SYNCED 0.7s before FLT-2210 was cleared; no shared id.", I1)
# --- INC-001 : B-side fault chain
FLOW("i1_f_B_notice", "i1_f_A_notice_B", "MSG-775", I1)
X("i1_f_A_notice_B", "i1_s_A_peerB_deg", "MSG-775", I1)
X("i1_f_B_raise", "i1_f_B_notice", "FLT-2207", I1)
X("i1_op_ack_alert", "i1_f_B_raise", "FLT-2207", I1, note="Operator acknowledges the alert by fault code.")
RCV("i1_f_B_raise", "i1_f_B_rcv", "FLT-2207", I1)
RCV("i1_f_B_rcv", "i1_s_B_rec", "RCV-55", I1); RCV("i1_f_B_rcv", "i1_g_B_reinit", "RCV-55", I1)
RCV("i1_f_B_rcv", "i1_s_B_nom", "RCV-55", I1); RCV("i1_f_B_rcv", "i1_f_B_clear", "RCV-55", I1)
RCV("i1_f_B_raise", "i1_f_B_clear", "FLT-2207", I1)
rel("i1_f_B_raise", "i1_f_B_clear", "RECOVERY", "strong", "Same fault code FLT-2207; duration_s=20 matches 09:41:09 -> 09:41:29.", I1, "FLT-2207")
# --- INC-001 : plausible-but-not-provable
rel("i1_g_B_apply", "i1_f_B_raise", "SHARED_COMPONENT", "medium",
    "Both concern NAV_FILTER on NODE_B, 1.75s apart. The fault record carries no plan or command id. Applying PLN-310 is a plausible contributor, but causation is NOT established by the available records.", I1, label="POSSIBLE")
rel("i1_g_B_dev1", "i1_s_B_deg", "SHARED_COMPONENT", "medium", "NAV_FILTER deviation 0.6s before NAV_FILTER state went DEGRADED; no explicit id.", I1)
rel("i1_s_B_deg", "i1_f_B_raise", "SHARED_COMPONENT", "medium", "NAV_FILTER DEGRADED 0.1s before FLT-2207 raised (fault is second-resolution); no explicit id.", I1)
rel("i1_op_submit1", "i1_f_B_raise", "TEMPORAL", "weak", "Operator command ~7s before the fault, on a different node, no shared id. Temporal association only; do not state causation.", I1, label="INSUFFICIENT_EVIDENCE")
rel("i1_f_B_raise", "i1_f_C_timeout1", "TEMPORAL", "weak", "Faults on different nodes and components 7s apart. Both follow PLN-310 distribution, but independence cannot be excluded.", I1, label="INSUFFICIENT_EVIDENCE")
rel("i1_op_B_query", "i1_f_B_raise", "SHARED_COMPONENT", "weak", "Operator on NODE_B queried NAV_FILTER 3.5s after the fault; plausible reaction, no explicit reference.", I1, label="POSSIBLE")
rel("i1_f_B_clear", "i1_s_A_peerB_ok", "TEMPORAL", "medium", "A's view of NODE_B returned to NOMINAL 0.2s after FLT-2207 cleared; no notice id referenced (source of A's information not in logs).", I1)
rel("i1_f_C_clear", "i1_s_A_peerC_ok", "TEMPORAL", "medium", "A's view of NODE_C returned to NOMINAL 0.4s after FLT-2210 cleared; no notice id referenced.", I1)
# --- INC-002
I2 = "INC-002"
X("i2_op_cmd", "i2_s_A", "CMD-1018", I2); X("i2_op_cmd", "i2_g_A_sent", "CMD-1018", I2)
FLOW("i2_g_A_sent", "i2_g_C_recv", "SP-044", I2, note="Setpoint SP-044 sent by A, received by C; both also carry CMD-1018.")
X("i2_g_C_recv", "i2_s_C", "SP-044", I2); X("i2_g_C_recv", "i2_f_C_raise", "SP-044", I2, note="Fault names the setpoint just received. The fault states out-of-range; the logs do not give the numeric value.")
RCV("i2_f_C_raise", "i2_f_C_rcv", "FLT-1304", I2); RCV("i2_f_C_rcv", "i2_s_C_rev", "RCV-61", I2); RCV("i2_f_C_rcv", "i2_f_C_clear", "RCV-61", I2)
rel("i2_f_C_raise", "i2_f_C_clear", "RECOVERY", "strong", "Same fault code FLT-1304; duration_s=2.", I2, "FLT-1304")
X("i2_g_C_reject", "i2_f_C_raise", "FLT-1304", I2); X("i2_g_C_reject", "i2_g_C_recv", "SP-044", I2)
rel("i2_g_A_sent", "i2_g_C_recv", "SEQUENCE", "strong", "SETPOINT_SENT -> SETPOINT_RECEIVED observed; the expected SETPOINT_ACK / SETPOINT_APPLIED steps are absent (sequence incomplete).", I2, "SP-044", seqpat="SENT->RECV->ACK->APPLIED->COMPLETE")
rel("i2_op_A_query", "i2_s_A", "SHARED_COMPONENT", "weak", "A operator queried SPEED_CTRL ~7.5s after A's SPEED_CTRL went ADJUSTING; possible follow-up, no reference.", I2, label="POSSIBLE")
rel("u2_f_A_jitter", "i2_g_A_sent", "TEMPORAL", "weak", "A-side link jitter 1.8s after setpoint send; the setpoint WAS received by C, so jitter is not shown to matter.", I2, label="INSUFFICIENT_EVIDENCE")
# --- INC-003 (normal)
I3 = "INC-003"
X("i3_op_cmd", "i3_s_A_step", "CMD-1030", I3); X("i3_op_cmd", "i3_g_A_sent", "CMD-1030", I3)
FLOW("i3_g_A_sent", "i3_g_C_recv", "SP-039", I3)
SEQ("i3_g_C_recv", "i3_g_C_ack", "SP-039", I3, "SENT->RECV->ACK->APPLIED->COMPLETE", "ACK_FOR=SP-039 follows receipt.")
SEQ("i3_g_C_ack", "i3_g_C_applied", "SP-039", I3, "SENT->RECV->ACK->APPLIED->COMPLETE", "Applied after ack.")
SEQ("i3_g_C_applied", "i3_g_A_done", "SP-039", I3, "SENT->RECV->ACK->APPLIED->COMPLETE", "Originator closes the cycle.")
X("i3_g_C_recv", "i3_s_C_step", "SP-039", I3); X("i3_s_A_step", "i3_s_A_end", "CMD-1030", I3); X("i3_s_C_step", "i3_s_C_end", "SP-039", I3)
for m, d in (("740", "B"), ("741", "C")):
    FLOW(f"i3_msg{m}_sent", f"i3_msg{m}_recv", f"MSG-{m}", I3)
    SEQ(f"i3_msg{m}_recv", f"i3_msg{m}_ack", f"MSG-{m}", I3, P4, "ACK follows receipt.")
    SEQ(f"i3_msg{m}_ack", f"i3_msg{m}_done", f"MSG-{m}", I3, P4, "Exchange completes.")

rel_out = []
for i, r in enumerate(RELS, 1):
    s, d = REG[r["src"]], REG[r["dst"]]
    rel_out.append({
        "relationship_id": f"REL-{i:03d}", "incident_id": r["inc"],
        "source_event_id": s["event_id"], "target_event_id": d["event_id"],
        "relationship_type": r["typ"], "strength": r["strength"], "uncertainty_label": r["label"],
        "shared_key": r["key"], "sequence_pattern": r["seqpat"],
        "delta_seconds": round((d["ts"] - s["ts"]).total_seconds(), 3),
        "causation_established": False, "reason": r["reason"],
        "source_label": r["src"], "target_label": r["dst"]})
dump("ground_truth/relationship_ground_truth.json", {
    "_notice": "GROUND TRUTH FOR EVALUATION ONLY. Never feed to the correlation engine. Synthetic prototype.",
    "_label_semantics": {"STRONG_SUPPORTED": "explicit shared id / explicit reference / message flow / documented sequence step",
                         "POSSIBLE": "plausible association (shared component and/or tight timing) but not provable from the records",
                         "INSUFFICIENT_EVIDENCE": "temporal proximity only; an AI narrative must NOT claim a cause"},
    "_note": "No relationship here asserts causation (causation_established is always false). TEMPORAL never implies cause.",
    "relationships": rel_out})

# ---- incident ground truth
def members(prefix): return sorted([t for t in REG if t.startswith(prefix)], key=lambda t: (REG[t]["ts"], REG[t]["line"]))
def lost_for(inc): return [dict(source_file=v["file"], source_line=v["line"], reason=v["reason"], raw_record=v["raw"],
                                probable_original={"timestamp": f_iso_ms(v["orig"]["ts"]), "node": v["orig"]["node"],
                                                   "log_family": v["orig"]["fam"], "event_type": v["orig"]["etype"], "message": v["orig"]["text"]})
                           for t, v in LOST.items() if v["incident"] == inc]
def nodes_of(tags): return sorted({REG[t]["node"] for t in tags})
def window(tags):
    ts = [REG[t]["ts"] for t in tags]; return [f_iso_ms(min(ts)), f_iso_ms(max(ts))]
def summ(tag_raise, tag_clear, tag_rcv):
    r, c = REG[tag_raise], REG[tag_clear]
    return {"fault_code": r["kv"]["code"], "fault_name": r["kv"]["name"], "node": r["node"], "component": r["comp"],
            "raised_event_id": r["event_id"], "cleared_event_id": c["event_id"], "recovery_event_id": eid(tag_rcv),
            "reported_duration_s": int(c["kv"]["dur"]), "computed_duration_s": int((c["ts"] - r["ts"]).total_seconds())}
def pairs(lst): return [{"source": lab(a), "target": lab(b), "why": w} for a, b, w in lst]

m1, m2, m3 = members("i1_"), members("i2_"), members("i3_")
incidents = [
    {"incident_id": "INC-001", "title": "Plan distribution followed by NAV_FILTER divergence (NODE_B) and plan-sync timeout (NODE_C)",
     "kind": "INCIDENT", "primary": True, "involved_nodes": nodes_of(m1), "time_window_utc": window(m1),
     "log_families_present": sorted({REG[t]["fam"] for t in m1}),
     "event_ids": labs(m1),
     "primary_fault": summ("i1_f_B_raise", "i1_f_B_clear", "i1_f_B_rcv"),
     "secondary_faults": [summ("i1_f_C_timeout1", "i1_f_C_clear", "i1_f_C_rcv")],
     "recovery_event": {"primary": lab("i1_f_B_rcv"), "secondary": lab("i1_f_C_rcv")},
     "expected_relationship_ids": [r["relationship_id"] for r in rel_out if r["incident_id"] == I1],
     "repeated_events": [
         {"description": "Operator resubmitted CMD-1042 (attempt 1 and 2)", "event_ids": [eid("i1_op_submit1"), eid("i1_op_submit2")]},
         {"description": "GUIDANCE_DEVIATION on NODE_B three times within ~1.2s (xte rising)", "event_ids": [eid("i1_g_B_dev1"), eid("i1_g_B_dev2"), eid("i1_g_B_dev3")]},
         {"description": "FLT-2210 raised twice as valid records; a third raise was lost to a malformed line", "event_ids": [eid("i1_f_C_timeout1"), eid("i1_f_C_timeout2")]}],
     "simultaneous_events": [
         {"description": "PROFILE_APPLY on NODE_B and NODE_C with identical millisecond timestamp", "event_ids": [eid("i1_g_B_apply"), eid("i1_g_C_apply")], "timestamp": f_iso_ms(REG["i1_g_B_apply"]["ts"])},
         {"description": "NODE_B FAULT_RAISED FLT-2207 and FAULT_NOTICE_SENT share the same second (fault family is second-resolution)", "event_ids": [eid("i1_f_B_raise"), eid("i1_f_B_notice")], "timestamp": f_iso_ms(REG["i1_f_B_raise"]["ts"])}],
     "intentionally_missing_events": [
         {"description": "MESSAGE_ACK for MSG-772 from NODE_C never logged (every other exchange in the dataset has an ACK)",
          "expected_after_event_id": eid("i1_msg772_recv"), "expected_pattern": P4,
          "absence_check": {"node": C, "log_family": "planning", "event_type": "MESSAGE_ACK", "key": "MSG-772"}},
         {"description": "EXCHANGE_COMPLETE for MSG-772 on NODE_A never logged",
          "expected_after_event_id": eid("i1_msg772_sent"), "expected_pattern": P4,
          "absence_check": {"node": A, "log_family": "planning", "event_type": "EXCHANGE_COMPLETE", "key": "MSG-772"}}],
     "malformed_records": lost_for("INC-001"),
     "unrelated_events_nearby": labs(["u1_op_C_display", "u1_f_A_jitter", "bg_gd_A_wp10", "bg_gd_B_wp10", "bg_gd_C_wp10"]),
     "relationships_that_should_not_be_inferred": pairs([
         ("i1_op_submit1", "i1_f_B_raise", "Do not say the operator command caused the divergence; only a ~7s temporal association exists."),
         ("i1_g_B_apply", "i1_f_B_raise", "Plausible, not provable: no id links profile application to the fault."),
         ("i1_f_B_raise", "i1_f_C_timeout1", "Do not say FLT-2207 caused FLT-2210; different node, component and no reference."),
         ("u1_f_A_jitter", "i1_f_C_timeout1", "A-side link jitter is not shown to explain the missing ACK."),
         ("u1_f_A_jitter", "i1_f_B_raise", "Unrelated transient warning on another component."),
         ("u1_op_C_display", "i1_f_B_raise", "Unrelated operator action (display brightness)."),
         ("bg_gd_A_wp10", "i1_f_B_raise", "Routine waypoint event on another node; unrelated.")]),
     "uncertainty_examples": {
         "CONFIRMED_OBSERVATION": [{"claim": "FLT-2207 NAV_FILTER_DIVERGENCE was raised on NODE_B at 09:41:09Z (second resolution).", "evidence": [eid("i1_f_B_raise")]}],
         "STRONG_SUPPORTED_RELATIONSHIP": [{"claim": "NODE_A sent plan PLN-310 as MSG-771 and NODE_B received and acknowledged it.", "evidence": [eid("i1_msg771_sent"), eid("i1_msg771_recv"), eid("i1_msg771_ack")]},
                                           {"claim": "The plan request PLN-310 was made under operator command CMD-1042.", "evidence": [eid("i1_op_submit1"), eid("i1_pl_req")]}],
         "POSSIBLE_RELATIONSHIP": [{"claim": "Applying PLN-310 may be related to the NAV_FILTER divergence; both involve NAV_FILTER within 2s, but causation is not established by the available records.", "evidence": [eid("i1_g_B_apply"), eid("i1_f_B_raise")]}],
         "INSUFFICIENT_EVIDENCE": [{"claim": "Whether FLT-2207 and FLT-2210 share a cause cannot be determined; they are temporally close only.", "evidence": [eid("i1_f_B_raise"), eid("i1_f_C_timeout1")]}],
         "MISSING_INFORMATION": [{"claim": "No acknowledgement of MSG-772 appears in NODE_C's records; why is unknown. A third FLT-2210 raise at ~09:41:22 may have been lost to a malformed line.", "evidence": [eid("i1_msg772_recv"), eid("i1_f_C_timeout2")]}]}},
    {"incident_id": "INC-002", "title": "Out-of-range speed setpoint rejected by NODE_C (smaller, two-node incident)",
     "kind": "INCIDENT", "primary": False, "involved_nodes": nodes_of(m2), "time_window_utc": window(m2),
     "log_families_present": sorted({REG[t]["fam"] for t in m2}),
     "event_ids": labs(m2),
     "primary_fault": summ("i2_f_C_raise", "i2_f_C_clear", "i2_f_C_rcv"), "secondary_faults": [],
     "recovery_event": {"primary": lab("i2_f_C_rcv")},
     "expected_relationship_ids": [r["relationship_id"] for r in rel_out if r["incident_id"] == I2],
     "repeated_events": [],
     "simultaneous_events": [{"description": "NODE_C FLT-1304 raised and NODE_A unrelated link-jitter warning share the same second on different nodes", "event_ids": [eid("i2_f_C_raise"), eid("u2_f_A_jitter")], "timestamp": f_iso_ms(REG["i2_f_C_raise"]["ts"])}],
     "intentionally_missing_events": [
         {"description": "SETPOINT_ACK for SP-044 from NODE_C (complete exchanges elsewhere, e.g. SP-039, have it)", "expected_after_event_id": eid("i2_g_C_recv"), "expected_pattern": "SENT->RECV->ACK->APPLIED->COMPLETE",
          "absence_check": {"node": C, "log_family": "guidance", "event_type": "SETPOINT_ACK", "key": "SP-044"}},
         {"description": "SETPOINT_APPLIED for SP-044 on NODE_C", "expected_after_event_id": eid("i2_g_C_recv"), "expected_pattern": "SENT->RECV->ACK->APPLIED->COMPLETE",
          "absence_check": {"node": C, "log_family": "guidance", "event_type": "SETPOINT_APPLIED", "key": "SP-044"}},
         {"description": "NODE_A SPEED_CTRL never returns ADJUSTING->STABLE in the supplied logs (A is left ADJUSTING)", "expected_after_event_id": eid("i2_s_A"), "expected_pattern": "STATE ADJUSTING->STABLE",
          "absence_check": {"node": A, "log_family": "state", "event_type": "STATE_CHANGE", "key": ";SPEED_CTRL;ADJUSTING;STABLE;"}}],
     "malformed_records": [],
     "unrelated_events_nearby": labs(["u2_f_A_jitter", "u2_op_B_note"]),
     "relationships_that_should_not_be_inferred": pairs([
         ("u2_f_A_jitter", "i2_f_C_raise", "A-side link jitter does not explain a C-side range fault; simultaneous second only."),
         ("u2_op_B_note", "i2_f_C_raise", "NODE_B is not part of this incident."),
         ("i2_op_cmd", "i2_f_C_raise", "Explicit chain exists via SP-044, but the logs do not state the numeric value; do not claim the operator 'caused' the fault beyond the referenced chain.")]),
     "uncertainty_examples": {
         "CONFIRMED_OBSERVATION": [{"claim": "NODE_C raised FLT-1304 and cleared it 2s later.", "evidence": [eid("i2_f_C_raise"), eid("i2_f_C_clear")]}],
         "STRONG_SUPPORTED_RELATIONSHIP": [{"claim": "FLT-1304 concerns setpoint SP-044, which NODE_C received from NODE_A for CMD-1018.", "evidence": [eid("i2_g_A_sent"), eid("i2_g_C_recv"), eid("i2_f_C_raise")]}],
         "POSSIBLE_RELATIONSHIP": [{"claim": "The NODE_A operator status query may be a follow-up to the adjustment.", "evidence": [eid("i2_op_A_query"), eid("i2_s_A")]}],
         "INSUFFICIENT_EVIDENCE": [{"claim": "Link jitter on NODE_A is not shown to be involved.", "evidence": [eid("u2_f_A_jitter")]}],
         "MISSING_INFORMATION": [{"claim": "NODE_A's SPEED_CTRL state is never reported back to STABLE; its final state is unknown.", "evidence": [eid("i2_s_A")]}]}},
    {"incident_id": "INC-003", "title": "Routine altitude profile step and plan sync (NORMAL OPERATION - not a fault incident)",
     "kind": "NON_INCIDENT_NORMAL_OPERATION", "primary": False, "involved_nodes": nodes_of(m3), "time_window_utc": window(m3),
     "log_families_present": sorted({REG[t]["fam"] for t in m3}),
     "event_ids": labs(m3), "primary_fault": None, "secondary_faults": [], "recovery_event": None,
     "expected_relationship_ids": [r["relationship_id"] for r in rel_out if r["incident_id"] == I3],
     "repeated_events": [], "simultaneous_events": [
         {"description": "Near-simultaneous plan-sync sends from NODE_A to NODE_B and NODE_C (within 500 ms)", "event_ids": [eid("i3_msg740_sent"), eid("i3_msg741_sent")], "timestamp": None, "tolerance_ms": 500}],
     "intentionally_missing_events": [], "malformed_records": [],
     "unrelated_events_nearby": labs(["u3_f_C_warn", "u3_op_B_query"]),
     "relationships_that_should_not_be_inferred": pairs([
         ("u3_f_C_warn", "i3_g_C_applied", "A 1-second self-cleared transient warning is not a fault incident and not linked to the setpoint step."),
         ("i3_op_cmd", "u3_f_C_warn", "Routine command is not related to the transient bus retry.")]),
     "uncertainty_examples": {"CONFIRMED_OBSERVATION": [{"claim": "CMD-1030 completed normally with a full SENT->RECV->ACK->APPLIED->COMPLETE sequence.", "evidence": [eid("i3_g_A_sent"), eid("i3_g_C_ack"), eid("i3_g_A_done")]}]},
     "notes": "Must NOT be reported as a fault incident. It is the control group for the 'normal vs incident' decision and for complete-sequence detection."}]
# simultaneous event ids for INC-003 are not exactly equal timestamps; mark tolerance and drop strict timestamp
incidents[2]["simultaneous_events"][0].pop("timestamp")

background = {
    "repeated_event_groups": [
        {"description": "Periodic SELFTEST_PASS on each node (cycle 1..15)", "event_ids": {n: [eid(f"bg_flt_{n[-1]}_st{k}") for k in range(1, 16) if f"bg_flt_{n[-1]}_st{k}" in REG] for n in NODES}},
        {"description": "Periodic GUIDANCE_STATUS heartbeat (hb 1..9)", "event_ids": {n: [eid(f"bg_gd_{n[-1]}_hb{k}") for k in range(1, 10) if f"bg_gd_{n[-1]}_hb{k}" in REG] for n in NODES}}],
    "simultaneous_events": [
        {"description": "WAYPOINT_REACHED WP-005 on NODE_A and NODE_C share the exact millisecond", "event_ids": [eid("bg_gd_A_wp05"), eid("bg_gd_C_wp05")], "timestamp": f_iso_ms(REG["bg_gd_A_wp05"]["ts"])},
        {"description": "PHASE_CHANGE CLIMB->CRUISE on NODE_A and NODE_C share the exact millisecond", "event_ids": [eid("bg_sta_A_ph2"), eid("bg_sta_C_ph2")], "timestamp": f_iso_ms(REG["bg_sta_A_ph2"]["ts"])}],
    "intentionally_missing_events": [
        {"description": "NODE_B never logs WAYPOINT_REACHED WP-012 (NODE_A and NODE_C do) - background gap unrelated to any incident",
         "absence_check": {"node": B, "log_family": "guidance", "event_type": "WAYPOINT_REACHED", "key": "wp=WP-012"}}],
    "malformed_records_not_in_incidents": [dict(source_file=v["file"], source_line=v["line"], reason=v["reason"], raw_record=v["raw"],
                                                probable_original={"timestamp": f_iso_ms(v["orig"]["ts"]), "node": v["orig"]["node"], "log_family": v["orig"]["fam"], "event_type": v["orig"]["etype"], "message": v["orig"]["text"]})
                                           for t, v in LOST.items() if v["incident"] is None],
    "lost_record_side_effects": [
        "MSG-703 (NODE_A->NODE_B): the SENT record on NODE_A is malformed, but RECEIVED/ACK/COMPLETE exist -> sender side must be flagged as missing/unparseable.",
        "NODE_A state seq has a gap where the malformed CONDITION_SAMPLE was; NODE_C SENSOR_BUS RETRY->NOMINAL at ~10:08:31 has no preceding NOMINAL->RETRY (its first half is malformed)."],
    "out_of_order_records": [{"file": FILES[(n, f)]["path"], "moved_event_id": eid(t), "placed": how, "relative_to_event_id": eid(a),
                              "note": "file order differs from timestamp order"} for (n, f, t, how, a) in MOVES]}

dump("ground_truth/incident_ground_truth.json", {
    "_notice": "GROUND TRUTH FOR EVALUATION ONLY. Never feed to the ingest/correlation engine. Synthetic prototype - not official data.",
    "dataset_id": "PS3-SYNTH-PROTO-v1", "incidents": incidents, "background_features": background})

# ================================================================= MANIFEST
def inc_of_tag(t):
    return {"i1": "INC-001", "i2": "INC-002", "i3": "INC-003"}.get(t[:2]) if t and t[:2] in ("i1", "i2", "i3") and t[2] == "_" else None


manifest = {"_notice": "SYNTHETIC PROTOTYPE dataset manifest. total_raw_lines = header_lines + expected_valid_records + expected_malformed_records.",
            "files": []}
for node in NODES:
    for fam in FAMS:
        m = FILES[(node, fam)]
        incs = {inc_of_tag(e["tag"]) for e in m["valid"]} - {None}
        incs |= {v["incident"] for v in LOST.values() if v["file"] == m["path"] and v["incident"]}
        manifest["files"].append({
            "path": m["path"], "node": node, "log_family": fam, "format": {"operator": "bracketed key=value", "planning": "CSV (12 columns, header on line 1)",
            "guidance": "whitespace-delimited key=value with epoch timestamp", "state": "semicolon-separated positional (9 fields)",
            "fault_recovery": "pipe-separated positional (10 fields)"}[fam],
            "total_raw_lines": len(m["lines"]), "header_lines": m["header"], "expected_valid_records": len(m["valid"]),
            "expected_malformed_records": len(m["malformed"]), "malformed_line_numbers": m["malformed"],
            "incident_ids": sorted(incs)})
manifest["totals"] = {"files": 15, "total_raw_lines": sum(f["total_raw_lines"] for f in manifest["files"]),
                      "expected_valid_records": sum(f["expected_valid_records"] for f in manifest["files"]),
                      "expected_malformed_records": sum(f["expected_malformed_records"] for f in manifest["files"])}
dump("dataset_manifest.json", manifest)

# ================================================================= README
def raw_of(t): return REG[t]["raw"]
L = []
w = L.append
w("# AI-assisted multi-system log analysis and incident visualization\n")
w("Dataset 1 is a fictional synthetic prototype; it is not the official dataset or real operational data.\n")
w("> **This is synthetic prototype data.** It is NOT the official hackathon dataset, NOT real flight-management data, and contains no real aircraft, airport or system identifiers. "
  "Log-family names, raw formats, event vocabularies, IDs and fault codes are **prototype assumptions** that must be replaced when the official dataset arrives.\n")
w("Purpose: exercise the whole PS3 pipeline end to end:\n\n`RAW LOGS -> INGEST -> PARSE -> NORMALIZE -> CORRELATE -> TIMELINE -> INCIDENT MODEL -> 4-LEVEL VISUALIZATION -> EVIDENCE RETRIEVAL -> AI NARRATIVE`\n")
w("Regenerate with `python3 tools/generate_dataset.py` (deterministic). Verify with `python3 tools/validate_dataset.py`.\n")
w("## 1. Three tiers of content - keep them separate\n")
w("### 1a. Facts explicitly specified by the problem statement\n")
for s in ["Three cooperating instances (nodes) of a fictional flight-management system; treat as any distributed operational system.",
          "Five log families ingested from the three nodes into a common event model.",
          "Content themes: planning, guidance, operator interaction, state changes, faults, recovery.",
          "Correlate operator actions, state, guidance events and faults across nodes.",
          "Reconstruct the timeline through repetition, simultaneity and missing data.",
          "Evidence-linked conclusions with a plain-language narrative; uncertainty labels.",
          "Importer must report skipped records.",
          "Four visualization levels: 1 Flight overview (source/destination, time, phases, significant faults, recovery summary); 2 Fault/event detail (code, name, time, duration, impact, recovery, related events); 3 Operation context (aircraft conditions, system state, cross-node state); 4 Evidence detail (source record).",
          "Filters by node, time, log family, event/fault category.",
          "Minimum demo: record totals across families; overview-to-evidence navigation; isolate one fault with filters; import-to-narrative end to end."]:
    w(f"- {s}")
w("\n### 1b. Prototype assumptions (NOT from the problem statement)\n")
for s in ["The five family names `operator, planning, guidance, state, fault_recovery`, and which raw syntax each uses.",
          "Node roles (A = primary operator/planner, B = guidance/navigation, C = monitor/standby) - purely a storytelling device.",
          "All event types, fault codes (`FLT-*`), recovery codes (`RCV-*`), command/message/plan/setpoint ids (`CMD-/MSG-/PLN-/SP-`), component names, waypoint ids.",
          "Timestamp formats per family, UTC, a fictional date (2031-05-12), second-resolution for the fault family.",
          "Fictional route `ZZ-ALPHA -> ZZ-BRAVO`, session `SIM-S01`, phases `PREFLIGHT/CLIMB/CRUISE/DESCENT/APPROACH`, 'condition' fields (`alt_band`, `spd_band`, `fuel_state`).",
          "The normalized event schema, `incident_hint`, `category`, `attributes` and the event-id scheme.",
          "That records are one-per-line and that malformed lines are simply unparseable lines."]:
    w(f"- {s}")
w("\n### 1c. Generated synthetic content\n")
w("Everything under `data/synthetic/`, plus the three JSON references and the manifest. Ground truth lives in `ground_truth/` and must **never** be an input to ingest/correlation.\n")
w("## 2. Layout\n")
w("```\ndata/synthetic/node_{A,B,C}/{operator,planning,guidance,state,fault_recovery}.log   <- 15 raw files (the only pipeline input)\ndata/synthetic/SYNTHETIC_NOTICE.txt\ndataset_manifest.json            <- expected counts per file (for import QA)\nnormalized_event_examples.json   <- 10 representative raw->normalized mappings (+ parsing rules)\nreference/parser_expected_events.json  <- full parser answer key (test your parser; not for correlation)\nground_truth/incident_ground_truth.json\nground_truth/relationship_ground_truth.json\ntools/generate_dataset.py, tools/validate_dataset.py\n```\n")
w("For convenient browsing, `data/dataset_1_bundle.txt` concatenates Dataset 1's 15 raw logs with source-file markers. It is a viewing aid only; ingest the original files under `data/synthetic/`, not the bundle. Future datasets should remain separately identified rather than merged into this Dataset 1 bundle.\n")
t = manifest["totals"]
w(f"**Totals:** {t['files']} files, {t['total_raw_lines']} raw lines = {t['expected_valid_records']} valid records + {t['expected_malformed_records']} malformed + 1 CSV header.\n")
w("| File | Format | Valid | Malformed | Lines |\n|---|---|---:|---:|---:|")
for f in manifest["files"]:
    w(f"| `{f['path'].replace('data/synthetic/', '')}` | {f['format']} | {f['expected_valid_records']} | {f['expected_malformed_records']} | {f['total_raw_lines']} |")
w("\n## 3. Raw formats (one real line each)\n")
for fam, tag in [("operator", "i1_op_submit1"), ("planning", "i1_msg771_sent"), ("guidance", "i1_g_B_dev1"), ("state", "i1_s_A_replan"), ("fault_recovery", "i1_f_B_raise")]:
    w(f"**{fam}** (`{ref(tag)}`)\n```\n{raw_of(tag)}\n```")
w("Planning header (line 1 of every `planning.log`): `" + ",".join(PL_COLS) + "`. Guidance uses epoch seconds; state uses compact `YYYYMMDDTHHMMSS.mmmZ`; operator uses `ts=` ISO; fault_recovery is second-resolution.\n")
w("## 4. Incidents\n")
w("| ID | Kind | Nodes | Window (UTC) | Purpose |\n|---|---|---|---|---|")
for i in incidents:
    w(f"| {i['incident_id']} | {i['kind']} | {', '.join(n[-1] for n in i['involved_nodes'])} | {i['time_window_utc'][0][11:19]} - {i['time_window_utc'][1][11:19]} | {i['title']} |")
w("\n## 5. Walkthrough - INC-001 (main demo incident)\n")
w("Raw records in time order (`event_id` = `EVT-<node>-<family>-<line>`; the line number IS the evidence pointer). Fault records have second resolution, so ordering inside the same second relies on other families.\n")
w("| Time (UTC) | Node | Family | Event type | Event ID | Source | What the record says |\n|---|---|---|---|---|---|---|")
for tg in m1:
    e = REG[tg]
    w(f"| {f_iso_ms(e['ts'])[11:23]} | {e['node'][-1]} | {e['fam']} | {e['etype']} | `{e['event_id']}` | `{e['file'].replace('data/synthetic/', '')}:{e['line']}` | {e['text']} |")
w("\n**Expected reconstructed story (what a good narrative may say):**\n")
w("1. *Confirmed:* operator on A submitted CMD-1042 (twice: attempt 1 and 2); A started replanning and requested plan PLN-310 under that command. *Strong (explicit ids).*")
w("2. *Confirmed:* A computed PLN-310 and sent it as MSG-771 to B and MSG-772 to C. B received and ACKed MSG-771; the exchange completed. *Strong (message flow + sequence).*")
w("3. *Confirmed:* B and C applied the profile at the same instant (07.250), then B reported three GUIDANCE_DEVIATION records, NAV_FILTER went DEGRADED, and FLT-2207 NAV_FILTER_DIVERGENCE was raised at 09:41:09. B notified A (MSG-775).")
w("4. *Possible, not provable:* the plan application and the divergence both involve NAV_FILTER within ~2 s, but no record links them - **causation is not established by the available records.**")
w("5. *Missing information:* C received MSG-772 but no ACK exists; C raised FLT-2210 PLAN_SYNC_TIMEOUT (referencing MSG-772), repeated it, and one more repeat appears only as a malformed line. The reason for the missing ACK is unknown.")
w("6. *Recovery (strong):* B started RCV-55 (filter reinit) -> NAV_FILTER RECOVERING -> NOMINAL -> FLT-2207 cleared after 20 s. C requested a resend; A sent MSG-779 (`resend_of=MSG-772`), C ACKed it, PLAN_SYNC SYNCED, FLT-2210 cleared after 11 s. The operator acknowledged FLT-2207.")
w("7. *Insufficient evidence:* FLT-2207 and FLT-2210 are 7 s apart on different nodes/components; do not claim one caused the other. Unrelated nearby: C display brightness change, A link-jitter warning, routine waypoint WP-010.\n")
w("Visualization mapping: **L1** session origin/dest (operator `SESSION_START`), phases (`PHASE_CHANGE`), the two faults and recoveries; **L2** code/name/duration/`related` fields in `fault_recovery`; **L3** `CONDITION_SAMPLE`, `STATE_CHANGE`, `PEER_STATE` (cross-node); **L4** `source_file:source_line` + `raw_record`.\n")
w("## 6. Correlation opportunities (fields/patterns)\n")
for s in ["**Shared identifiers:** `cmd_id`/`cmd_ref`/`cmd` (CMD-1042, 1018, 1030), `plan_id` (PLN-310), `sp` (SP-044, SP-039), fault code `FLT-*`, recovery code `RCV-*`.",
          "**Explicit references:** planning `ack_for`, `resend_of`; state `trigger`; guidance `ref`; fault `related`; operator `alert_id`.",
          "**Message flow:** `MESSAGE_SENT` (peer=dst) on one node <-> `MESSAGE_RECEIVED` (peer=src) on another with the same `msg_id`; fault-notice flow via `related=MSG-775/776` (`FAULT_NOTICE_SENT` -> `PEER_FAULT_NOTICE`); setpoint flow via `sp`.",
          "**Shared component:** `component` (NAV_FILTER, PLAN_SYNC, SPEED_CTRL, COMM_LINK...) and `PEER_NODE_x` components for cross-node state.",
          "**Temporal proximity:** weak by itself; use with a window (e.g. <= 10 s) and never as causation.",
          "**Sequences:** `SEND->RECV->ACK->COMPLETE` (planning), `SENT->RECV->ACK->APPLIED->COMPLETE` (guidance setpoints), `RAISED->RECOVERY_STARTED->CLEARED` (faults), state `from->to` chains. Absence of an expected step is itself a finding.",
          "**Repetition keys:** same node+family+type+key repeated (attempt counters, `repeat N` text, hb counters).",
          "**State `seq`:** per-node monotonic counter; gaps indicate lost records and out-of-order placement."]:
    w(f"- {s}")
w("\n## 7. Edge-case index\n")
w("- **Repeated:** INC-001 operator resubmit; 3x GUIDANCE_DEVIATION on B; FLT-2210 raised twice (+1 malformed); periodic SELFTEST_PASS / GUIDANCE_STATUS series (non-incident repeats).")
w(f"- **Simultaneous:** `{ref('i1_g_B_apply')}` & `{ref('i1_g_C_apply')}` (same ms); WP-005 on A and C (`{ref('bg_gd_A_wp05')}`, `{ref('bg_gd_C_wp05')}`); phase change A/C (`{ref('bg_sta_A_ph2')}`, `{ref('bg_sta_C_ph2')}`); fault-family same-second ties.")
w("- **Missing (absent from raw logs, no placeholder):** ACK + COMPLETE for MSG-772 (INC-001); SETPOINT_ACK/APPLIED for SP-044 and A's ADJUSTING->STABLE (INC-002); NODE_B WP-012 (background).")
w("- **Malformed (skip + report):**")
for tg, v in LOST.items():
    w(f"  - `{v['file'].replace('data/synthetic/', '')}:{v['line']}` - {v['reason']}")
w("- **Out-of-order (file order != time order):**")
for (n, f, tg, how, a) in MOVES:
    w(f"  - `{ref(tg)}` is written {how} `{ref(a)}`")
w("- **Normal activity / unrelated:** INC-003 control group, periodic selftests/heartbeats/refreshes/waypoints, transient self-cleared warnings (`FLT-0901`, `FLT-0420`).\n")
w("## 8. Parser guidance (Python)\n")
w("One small parser per family returning `None`/raising on malformed input; the importer counts and records skips with `(file, line, reason, raw)`.\n")
w("```python\nimport csv, re, shlex\nKV = re.compile(r'\\s*(\\w+)=(\"[^\"]*\"|[^\\s\"]+)')\ndef parse_operator(line):   # [ts=..][node=..][sev=..] k=v ... msg=\"..\"\n    m = re.match(r'^\\[ts=([^\\]]+)\\]\\[node=(NODE_[ABC])\\]\\[sev=(\\w+)\\] (.*)$', line)\n    if not m: raise ValueError('bad_prefix')\n    # scan k=v tokens; any leftover text => ValueError('incomplete_key_value')\ndef parse_planning(line):   # csv.reader, expect 12 columns, non-empty ts\ndef parse_guidance(line):   # split(); float(ts); node; 'GDN'; every other token must be k=v\ndef parse_state(line):      # split(';') -> 9 fields; int(seq)\ndef parse_fault(line):      # split('|') -> 10 fields; event matches ^[A-Z_]+$\n```\n")
w("Steps: (1) iterate files with `enumerate(f, 1)` so the line number is the evidence pointer; (2) skip the planning header; (3) parse -> normalize (UTC ms) -> `event_id = EVT-<n>-<fam>-<line>`; (4) on failure append to a skipped-record report (file, line, reason, raw); (5) sort by timestamp but keep `source_line` (and state `seq`) for tie-breaks and out-of-order detection; (6) compare your counts with `dataset_manifest.json`. `tools/validate_dataset.py` contains a complete reference implementation of the five parsers.\n")
w("## 9. Using the ground truth (evaluation only)\n")
w("Score your correlation engine by precision/recall on `relationship_ground_truth.json`; check that every pair in `relationships_that_should_not_be_inferred` is NOT presented as causal; check the narrative uses the right uncertainty label per `uncertainty_examples`; check INC-003 is not reported as a fault incident; check missing-event detection against `intentionally_missing_events`.\n")
w("## 10. What to replace when the official dataset arrives\n")
for s in ["Family names, raw formats, parsers and timestamp formats.", "Event vocabulary, categories, fault/recovery codes and their meaning, severity scale.",
          "Identifier schemes (CMD/MSG/PLN/SP) and which fields carry cross-node references.", "Node roles and component names.",
          "Phase model, route fields and aircraft-condition fields used for Level 1 and Level 3.", "The normalized schema and `event_id` scheme.",
          "All ground-truth files (re-derive from the official data), the manifest, and the incident definitions.",
          "Keep: the architecture, the relationship taxonomy, the uncertainty-label vocabulary, and the validator's *kinds* of checks."]:
    w(f"- {s}")
w("\n## 11. Validation\n")
w("`python3 tools/validate_dataset.py` independently re-parses every raw line and checks: manifest counts, line/ID references, shared ids, message flows, missing events really absent, repeats/simultaneity real, malformed lines really unparseable, out-of-order present, normal and unrelated events present, no ground-truth leakage into raw logs, no real-aviation markers.\n")
with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(L) + "\n")

# Produce one readable, deterministic browsing copy of Dataset 1. Keep each
# original file intact because those files are the actual ingestion inputs.
bundle_paths = [
    os.path.join("data", "synthetic", f"node_{node}", f"{family}.log")
    for node in "ABC"
    for family in FAMS
]
bundle = [
    "# PS3 Synthetic Dataset 1 — bundled raw logs",
    "# Fictional prototype data; not an official dataset or real operational data.",
    "# Browse this file; use the individual data/synthetic/node_*/ files for ingestion.",
    "",
]
for relative_path in bundle_paths:
    bundle.extend((f"===== BEGIN {relative_path.replace(os.sep, '/')} =====",))
    with open(os.path.join(ROOT, relative_path), encoding="utf-8") as source:
        bundle.extend(source.read().splitlines())
    bundle.extend((f"===== END {relative_path.replace(os.sep, '/')} =====", ""))

with open(os.path.join(ROOT, "data", "dataset_1_bundle.txt"), "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(bundle))

print("OK  valid=%d malformed=%d lines=%d" % (manifest["totals"]["expected_valid_records"], manifest["totals"]["expected_malformed_records"], manifest["totals"]["total_raw_lines"]))
for f in manifest["files"]:
    print(f"  {f['path']:50s} valid={f['expected_valid_records']:3d} bad={f['expected_malformed_records']} lines={f['total_raw_lines']}")
