from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from chesslab.adaptive import RecoveryGate
from chesslab.coach import Coach
from chesslab.config import BoardBox


def test_animation_grace_and_scan_cooldown():
    gate = RecoveryGate()
    assert not gate.should_scan(10,False,0)
    assert not gate.should_scan(10.8,False,0)
    assert not gate.should_scan(10.9,True,0)
    assert not gate.should_scan(11,False,0)
    assert gate.should_scan(12.1,False,0)
    assert not gate.should_scan(12.2,False,12.1)
    assert gate.should_scan(15.2,False,12.1)


def test_scan_queue_does_not_block_vision_queue():
    stop = Event()
    vision = ThreadPoolExecutor(max_workers=1)
    scan = ThreadPoolExecutor(max_workers=1)
    try:
        pending = scan.submit(stop.wait,3)
        assert vision.submit(lambda:'frame processed').result(timeout=1) == 'frame processed'
        assert not pending.done()
    finally:
        stop.set(); scan.shutdown(); vision.shutdown()


def test_normal_frame_change_never_triggers_periodic_scan(monkeypatch):
    from chesslab import coach as module
    c = Coach.__new__(Coach)
    c.running,c.closed,c.generation = True,False,1
    c.pending_layout = None
    c.target,c.target_rect = 7,(0,0,900,900)
    c.force_scan = False
    c.last_scan,c.last_visual_change = 1,100
    c.overlay = SimpleNamespace(capture_excluded=True)
    c._visible = lambda:True
    events=[]
    c._capture=lambda token:events.append('capture')
    c._rescan=lambda token:events.append('scan')
    monkeypatch.setattr(module,'rect',lambda _:c.target_rect)
    c._cycle(1)
    assert events == ['capture']


def test_same_geometry_does_not_clear_cache(monkeypatch):
    from chesslab import coach as module
    c = Coach.__new__(Coach)
    box=BoardBox(10,10,810,810)
    c.settings=SimpleNamespace(board=box)
    c.running,c.closed,c.generation=True,False,1
    c.target,c.target_rect=7,(0,0,900,900)
    c.pending_layout=None
    c.status=SimpleNamespace(set=lambda _:None)
    c.scan_future=Future(); c.scan_future.set_result(box)
    monkeypatch.setattr(module,'rect',lambda _:c.target_rect)
    c._scan_result(1,c.target_rect,box,c.scan_future)
    assert c.pending_layout is None


def test_stale_scan_result_discarded():
    c=Coach.__new__(Coach)
    c.running,c.closed,c.generation=True,False,2
    c.pending_layout=None
    stale=Future(); stale.set_result(BoardBox(1,1,801,801))
    c.scan_future=Future()
    c._scan_result(1,(0,0,900,900),None,stale)
    assert c.pending_layout is None
