import yaml
from scanner.providers.sample import SampleProvider
from scanner.providers.base import Bars
from scanner.detect import analyze

def test_signal_at_t_ignores_future():
    p = yaml.safe_load(open("config/settings.yaml"))["params"]
    prov = SampleProvider(); n = 0
    for u in prov.universe()[:30]:
        b = prov.history(u["ticker"], 250)
        for t in range(40, 240, 7):
            cut = Bars(b.dates[:t + 1], b.o[:t + 1], b.h[:t + 1], b.l[:t + 1], b.c[:t + 1], b.v[:t + 1])
            full, part = analyze(b, p, t), analyze(cut, p)
            assert full == part, (u["ticker"], t); n += bool(full)
    assert n > 0   # הבדיקה באמת בדקה אותות
