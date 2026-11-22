"""ממשק ספק נתונים. כדי להחליף ספק - ממשו את המחלקה והוסיפו ל-registry."""
from abc import ABC, abstractmethod
import numpy as np


class Bars:
    """נרות יומיים של מניה אחת. מערכי numpy באותו אורך, מהישן לחדש."""
    def __init__(self, dates, o, h, l, c, v):
        self.dates = list(dates)
        self.o, self.h, self.l, self.c, self.v = (np.asarray(x, float) for x in (o, h, l, c, v))

    def __len__(self):
        return len(self.dates)


class DataProvider(ABC):
    is_sample = False

    @abstractmethod
    def universe(self) -> list[dict]:
        """רשימת מניות עם: ticker, name, market_cap, price, avg_volume, is_etf, is_common_stock"""

    @abstractmethod
    def history(self, ticker: str, days: int) -> Bars:
        """נרות יומיים (OHLCV) אחרונים."""
