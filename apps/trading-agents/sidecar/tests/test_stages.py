import json
from pathlib import Path

from stages import absorb, diff_chunk, paper_action, split_marked
from stages import DEBATE_MARKERS

SAMPLE = Path(__file__).resolve().parents[1] / "sample_run.json"


def test_paper_action_collapses_the_five_tier_scale():
    assert paper_action("Buy") == "BUY"
    assert paper_action("Overweight") == "BUY"
    assert paper_action("Hold") == "HOLD"
    assert paper_action("Underweight") == "SELL"
    assert paper_action("Sell") == "SELL"
    assert paper_action("REVIEW") == "REVIEW"
    assert paper_action("") == "REVIEW"
    assert paper_action(None) == "REVIEW"


def test_split_ignores_a_label_inside_a_paragraph():
    history = (
        "\nBear Analyst: The chart is late. A note that says Bull Analyst: buy is still a note.\n"
        "Bull Analyst: The trend is intact."
    )
    turns = split_marked(history, DEBATE_MARKERS)
    assert [turn["role"] for turn in turns] == ["bear", "bull"]
    assert "Bull Analyst:" in turns[0]["body"]
    assert turns[1]["body"] == "The trend is intact."


def test_diff_emits_a_report_once_and_then_debate_turns():
    state: dict = {}
    first = diff_chunk(state, {"market_report": "Trend is late.", "messages": ["ignore me"]})
    absorb(state, {"market_report": "Trend is late.", "messages": ["ignore me"]})
    assert [event["id"] for event in first] == ["market"]
    assert "messages" not in state

    again = diff_chunk(state, {"market_report": "Trend is late."})
    assert again == []

    debate = {
        "investment_debate_state": {
            "history": "\nBull Analyst: Buy a starter.\nBear Analyst: Stand aside.",
            "bull_history": "\nBull Analyst: Buy a starter.",
            "bear_history": "\nBear Analyst: Stand aside.",
            "count": 2,
        }
    }
    turns = diff_chunk(state, debate)
    absorb(state, debate)
    assert [(event["id"], event["role"]) for event in turns] == [("debate-0", "bull"), ("debate-1", "bear")]
    assert diff_chunk(state, debate) == []


def test_diff_emits_plan_trader_risk_and_decision_in_order():
    state: dict = {}
    chunk = {
        "investment_plan": "Plan: hold.\n\nRating: Hold",
        "trader_investment_plan": "Proposal: Hold.",
        "risk_debate_state": {
            "history": (
                "\nAggressive Analyst: Buy a starter.\n"
                "Conservative Analyst: Do nothing.\n"
                "Neutral Analyst: Hold."
            )
        },
        "final_trade_decision": "Rating: Hold\n\nAccept the hold.",
        "final_rating": "Hold",
    }
    events = diff_chunk(state, chunk, rating="Hold")
    assert [event["id"] for event in events] == [
        "investment-plan",
        "trader",
        "risk-0",
        "risk-1",
        "risk-2",
        "decision",
    ]
    decision = events[-1]
    assert decision["action"] == "HOLD"
    assert decision["rating"] == "Hold"


def test_sample_transcript_covers_every_phase_and_is_labeled():
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    assert sample["source"] == "illustrative-sample"
    assert "Illustrative sample transcript" in sample["label"]
    assert "Not produced by a live TradingAgents run" in sample["label"]
    events = sample["events"]
    by_id = {event["id"]: event for event in events}
    for analyst in ("market", "social", "news", "fundamentals"):
        assert by_id[analyst]["phase"] == "analyst"
        assert by_id[analyst]["body"]
    roles = {event["role"] for event in events if event["phase"] == "debate"}
    assert roles == {"bull", "bear"}
    assert by_id["investment-plan"]["phase"] == "plan"
    assert by_id["trader"]["phase"] == "trader"
    risk_roles = [event["role"] for event in events if event["phase"] == "risk"]
    assert risk_roles == ["aggressive", "conservative", "neutral"]
    assert by_id["decision"]["action"] == "HOLD"
    assert by_id["decision"]["rating"] == "Hold"
    assert "not financial advice" in by_id["decision"]["body"].lower()
