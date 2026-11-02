"""Moonpetal fairy friendship + house secret. Run: python3 tools/test_fairy_friendship.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)
import fairy_friendship as FF  # noqa: E402


def test_math_reaches_100():
    # 1 greet + 4 topics + 5 compliments = 4 + 40 + 60 = 104 → clamp 100
    assert FF.GREET_GAIN + 4 * FF.TOPIC_GAIN + 5 * FF.COMPLIMENT_GAIN >= FF.MAX


def test_full_trust_unlocks_secret():
    db = database.Database(":memory:")
    pid = 1
    d = FF.load(db.conn, pid)
    assert not FF.all_maxed(d)
    for fid in FF.FAIRY_IDS:
        d, _ = FF.greet(db.conn, pid, fid)
        for tid in FF.TOPICS:
            d, g, line = FF.apply_topic(db.conn, pid, fid, tid)
            assert line and len(line) > 40
            assert g in (0, FF.TOPIC_GAIN)
        for cid, _ in FF.COMPLIMENTS[fid]:
            d, g, line = FF.apply_compliment(db.conn, pid, fid, cid)
            assert 0 <= g <= FF.COMPLIMENT_GAIN
            assert line and len(line) > 20
    d = FF.load(db.conn, pid)
    assert FF.all_maxed(d)
    assert d["secret_unlocked"] is True
    assert "Petaldeep" in FF.secret_line(d)
    assert "corrupt" in FF.secret_line(d).lower()


def test_repeat_topic_no_double_dip():
    db = database.Database(":memory:")
    FF.greet(db.conn, 2, "selune")
    d, g1, _ = FF.apply_topic(db.conn, 2, "selune", "moon")
    assert g1 == FF.TOPIC_GAIN
    d, g2, _ = FF.apply_topic(db.conn, 2, "selune", "moon")
    assert g2 == 0
    assert d["friendship"]["selune"] == FF.GREET_GAIN + FF.TOPIC_GAIN


def test_partial_hint():
    db = database.Database(":memory:")
    d = FF.load(db.conn, 3)
    hint = FF.secret_line(d)
    assert "Petaldeep" not in hint
    assert "trust" in hint.lower()


if __name__ == "__main__":
    test_math_reaches_100()
    test_full_trust_unlocks_secret()
    test_repeat_topic_no_double_dip()
    test_partial_hint()
    print("test_fairy_friendship: OK")
