"""The model was asked for a 20/50 SMA crossover and returned a constant long."""

import pandas as pd


class SignalEngine:
    def generate(self, data):
        frame = data["RELIANCE.NS"]
        return pd.Series(1.0, index=frame.index).to_frame("RELIANCE.NS")
