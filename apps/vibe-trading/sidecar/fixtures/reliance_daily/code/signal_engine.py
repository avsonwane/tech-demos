"""20/50 SMA crossover written at the run root. No nested sma/ or bh/ folder."""


class SignalEngine:
    def generate(self, data):
        frame = data["RELIANCE.NS"]
        fast = frame["close"].rolling(20).mean()
        slow = frame["close"].rolling(50).mean()
        return (fast > slow).astype(float).to_frame("RELIANCE.NS")
