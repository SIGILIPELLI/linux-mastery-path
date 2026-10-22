from datetime import datetime as D
from cronexpr import Cron
import pytest
def test_every_5_minutes():
    c = Cron("*/5 * * * *"); assert c.matches(D(2026,10,21,10,15)) and not c.matches(D(2026,10,21,10,16))
def test_next_nightly():
    assert Cron("30 2 * * *").next_after(D(2026,10,21,3,0)) == D(2026,10,22,2,30)
def test_weekdays_only():
    c = Cron("0 9 * * 1-5"); assert c.matches(D(2026,10,21,9,0)) and not c.matches(D(2026,10,24,9,0))   # Wed yes, Sat no
def test_sunday_zero_and_seven():
    assert Cron("0 0 * * 0").dow == Cron("0 0 * * 7").dow == {0}
def test_names():
    assert Cron("0 0 1 jan,jul *").mon == {1, 7} and Cron("0 0 * * mon-fri").dow == {1,2,3,4,5}
def test_dom_dow_or_rule():
    c = Cron("0 0 13 * 5")       # the 13th OR any Friday - not 'Friday the 13th'
    assert c.matches(D(2026,10,13,0,0))      # Tuesday the 13th matches via day-of-month
    assert c.matches(D(2026,10,16,0,0))      # a Friday that is not the 13th matches via day-of-week
    assert not c.matches(D(2026,10,15,0,0))
def test_dom_only_and():
    c = Cron("0 0 13 * *"); assert c.matches(D(2026,10,13,0,0)) and not c.matches(D(2026,10,14,0,0))
def test_feb_30_never():
    assert Cron("0 0 30 2 *").next_after(D(2026,1,1,0,0), limit_days=800) is None
def test_bad_field():
    with pytest.raises(ValueError): Cron("61 * * * *")
    with pytest.raises(ValueError): Cron("* * * *")
def test_step_range():
    assert Cron("10-30/10 * * * *").min == {10, 20, 30}
