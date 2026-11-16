"""Buy and hold comparison. Not the requested strategy."""


class SignalEngine:
    def generate(self, data):
        frame = data["RELIANCE.NS"]
        return (frame["close"] * 0 + 1).to_frame("RELIANCE.NS")
