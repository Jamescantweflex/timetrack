import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from timetrack.engine import Engine  # noqa: E402

LIMITS = {
    "X": {"pause_on_open": True, "session_minutes": 10, "daily_minutes": 30, "block_after_daily": False},
    "YouTube": {"pause_on_open": False, "session_minutes": 20, "daily_minutes": 45, "block_after_daily": True},
}
SETTINGS = {"session_gap_seconds": 60, "grace_minutes": 10, "extension_minutes": 5}


def mk():
    return Engine(LIMITS, SETTINGS)


def test_pause_on_open_then_go_then_session_limit():
    e, t = mk(), 1000
    p = e.tick(t, "X", 0)
    assert p and p.kind == "pause"
    assert e.tick(t + 3, "X", 3) is None          # prompt open, nothing new
    e.answer(t + 5, "go")                         # 10 min allowance
    for dt in range(6, 600, 3):
        assert e.tick(t + dt, "X", dt) is None
    p = e.tick(t + 605, "X", 605)
    assert p and p.kind == "session" and p.session_seconds >= 600
    e.answer(t + 606, "more")                     # 5 more minutes
    for dt in range(607, 906, 3):
        assert e.tick(t + dt, "X", dt) is None
    p = e.tick(t + 910, "X", 910)
    assert p and p.kind == "session"


def test_bounce_then_reopen_prompts_again():
    e, t = mk(), 1000
    assert e.tick(t, "X", 0).kind == "pause"
    e.answer(t + 2, "bounce")
    assert e.tick(t + 5, "github.com", 0) is None
    p = e.tick(t + 30, "X", 10)                   # back within 30s: still a new session after bounce
    assert p and p.kind == "pause"


def test_leaving_makes_prompt_stale():
    e, t = mk(), 1000
    e.tick(t, "X", 0)
    e.tick(t + 10, "docs.google.com", 0)
    assert not e.stale_prompt(t + 30)
    assert e.stale_prompt(t + 80)
    e.answer(t + 80, "left")
    assert e.open_prompt is None
    # coming back after the gap is a new session -> pause again
    assert e.tick(t + 200, "X", 0).kind == "pause"


def test_no_pause_category_hits_session_limit_naturally():
    e, t = mk(), 5000
    for dt in range(0, 20 * 60, 3):
        assert e.tick(t + dt, "YouTube", dt) is None
    p = e.tick(t + 20 * 60, "YouTube", 1200)
    assert p and p.kind == "session" and not p.block


def test_daily_budget_and_block():
    e, t = mk(), 9000
    # YouTube over its 45 min budget, block_after_daily=True
    p = e.tick(t, "YouTube", 46 * 60)
    assert p and p.kind == "daily" and p.block
    e.answer(t + 1, "done")
    # X over budget: pause-on-open becomes a daily prompt, not blocking
    p = e.tick(t + 100, "X", 31 * 60)
    assert p and p.kind == "daily" and not p.block


def test_cooldown_prevents_double_prompt():
    e, t = mk(), 100
    assert e.tick(t, "X", 0).kind == "pause"
    e.answer(t + 1, "bounce")
    assert e.tick(t + 5, "X", 5) is None          # within 20 s cooldown
    assert e.tick(t + 25, "X", 25).kind == "pause"


def test_timeout_and_meditate_are_stops():
    e, t = mk(), 100
    assert e.tick(t, "X", 0).kind == "pause"
    e.answer(t + 70, "timeout")
    assert e.tick(t + 100, "X", 100).kind == "pause"      # back on X after a stop: asked again
    e.answer(t + 101, "meditate")
    assert e.tick(t + 130, "X", 130).kind == "pause"


def test_productive_reasks_every_allowance():
    e, t = mk(), 100
    e.tick(t, "X", 0); e.answer(t + 12, "go")             # 10 min allowance
    for dt in range(13, 612, 3):
        assert e.tick(t + dt, "X", dt) is None
    p = e.tick(t + 615, "X", 615); assert p and p.kind == "session"
    e.answer(t + 616, "more")                             # 5 min in the test settings
    for dt in range(617, 916, 3):
        assert e.tick(t + dt, "X", dt) is None
    assert e.tick(t + 920, "X", 920).kind == "session"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
