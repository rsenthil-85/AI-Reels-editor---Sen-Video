"""livelog.py - progress notes for the live edit page (live.py + templates/live.html).

The pipeline calls step()/note(); everything lands in <edit dir>/live.json, which the page polls every second.
Cheap and safe: any error here is swallowed so logging can never break an edit.
"""
import json, os, time

STEPS = [("analyse", "Listening to your video"), ("cut", "Cutting pauses, umms and retakes"), ("style", "Applying your style"),
         ("graphics", "Making the graphics"), ("render", "Putting the video together"), ("audio", "Cleaning voice, mixing music"),
         ("done", "Finished")]

def _path(edit_dir): return os.path.join(edit_dir, "live.json")

def _load(edit_dir):
    try: return json.load(open(_path(edit_dir), encoding="utf-8"))
    except Exception:
        return {"start": time.time(), "steps": {k: {"label": l, "state": "todo", "detail": ""} for k, l in STEPS},
                "order": [k for k, _ in STEPS], "notes": []}

def _save(edit_dir, d):
    tmp = _path(edit_dir) + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, _path(edit_dir))

def reset(edit_dir, **info):
    try:
        d = {"start": time.time(), "steps": {k: {"label": l, "state": "todo", "detail": ""} for k, l in STEPS},
             "order": [k for k, _ in STEPS], "notes": [], **info}
        _save(edit_dir, d)
    except Exception: pass

def step(edit_dir, key, state="doing", detail=None, **info):
    """state: todo | doing | done. detail: one short human line ("23 pauses cut")."""
    try:
        d = _load(edit_dir); s = d["steps"].setdefault(key, {"label": key, "state": "todo", "detail": ""})
        s["state"] = state
        if detail is not None: s["detail"] = detail
        if state == "doing": s["t0"] = time.time()
        if state == "done": s["t1"] = time.time()
        d.update(info); _save(edit_dir, d)
    except Exception: pass

def note(edit_dir, text, **info):
    try:
        d = _load(edit_dir); d["notes"].append({"t": round(time.time() - d.get("start", time.time()), 1), "text": text})
        d["notes"] = d["notes"][-60:]; d.update(info); _save(edit_dir, d)
    except Exception: pass
