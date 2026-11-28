"""wait_choice.py - wait until the user presses Start editing on the edit page, then print what they chose.

    python wait_choice.py [--timeout SECONDS]

Follows the page's current video (~/.pro-video-editor/current.json, written by live.py), so it also catches a video
the user uploaded with the page's "New video" button. Prints one JSON line and exits:
    {"video": "...", "edit_dir": "...", "choice": {...}}
and marks the choice as taken (<edit>/choice.taken) so the next wait does not return the same one. Run it again
after each edit to catch the next video. Exit code 2 on timeout. Standard library only.
"""
import json, os, sys, time

STATE = os.path.join(os.path.expanduser("~"), ".pro-video-editor", "current.json")
ALIVE = os.path.join(os.path.dirname(STATE), "agent.alive")   # live.py: an agent is listening (else it runs the automatic edit)

def main():
    a = sys.argv[1:]
    timeout = float(a[a.index("--timeout") + 1]) if "--timeout" in a else 0
    t0 = time.time()
    while True:
        try: open(ALIVE, "w").write(str(time.time()))
        except OSError: pass
        try:
            cur = json.load(open(STATE, encoding="utf-8")); ed = cur.get("edit_dir") or ""
            cp = os.path.join(ed, "choice.json")
            if ed and os.path.exists(cp) and not os.path.exists(os.path.join(ed, "choice.taken")):
                ch = json.load(open(cp, encoding="utf-8"))
                open(os.path.join(ed, "choice.taken"), "w").write("agent")
                try: os.remove(ALIVE)
                except OSError: pass
                print(json.dumps({"video": cur.get("video"), "edit_dir": ed, "choice": ch}, ensure_ascii=False), flush=True)
                return
        except (OSError, ValueError):
            pass   # live.py is writing the file right now: try again
        if timeout and time.time() - t0 > timeout:
            try: os.remove(ALIVE)
            except OSError: pass
            sys.exit(2)
        time.sleep(1)

if __name__ == "__main__":
    main()
