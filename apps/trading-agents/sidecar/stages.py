"""Turn TradingAgents state chunks into timeline events.

The graph files whole reports and appends debate turns. This module only
diffs those fields. It does not import TradingAgents, so the tests stay offline.
"""

from __future__ import annotations

REPORTS = (
    ("market_report", "market", "Market / technical"),
    ("sentiment_report", "social", "Sentiment"),
    ("news_report", "news", "News"),
    ("fundamentals_report", "fundamentals", "Fundamentals"),
)

DEBATE_MARKERS = (
    ("Bull Analyst:", "bull", "Bull researcher"),
    ("Bear Analyst:", "bear", "Bear researcher"),
)

RISK_MARKERS = (
    ("Aggressive Analyst:", "aggressive", "Aggressive risk"),
    ("Conservative Analyst:", "conservative", "Conservative risk"),
    ("Neutral Analyst:", "neutral", "Neutral risk"),
)

_SKIP_KEYS = {"messages"}


def paper_action(rating: str | None) -> str:
    """Collapse the library's 5-tier rating to the paper badge.

    Buy and Overweight are BUY, Hold is HOLD, Underweight and Sell are SELL.
    Anything else, including the library's REVIEW sentinel, stays REVIEW.
    """

    key = (rating or "").strip().lower()
    if key in {"buy", "overweight"}:
        return "BUY"
    if key == "hold":
        return "HOLD"
    if key in {"sell", "underweight"}:
        return "SELL"
    return "REVIEW"


def split_marked(history: str, markers: tuple[tuple[str, str, str], ...]) -> list[dict[str, str]]:
    """Split a debate log on speaker labels that start a line.

    TradingAgents stores ``history + "\\n" + "Bull Analyst: ..."``. A label
    inside a paragraph does not start a new turn.
    """

    text = history or ""
    hits: list[tuple[int, str, str, str]] = []
    for label, role, title in markers:
        start = 0
        while True:
            index = text.find(label, start)
            if index < 0:
                break
            if index == 0 or text[index - 1] == "\n":
                hits.append((index, label, role, title))
            start = index + len(label)
    hits.sort(key=lambda item: item[0])
    turns: list[dict[str, str]] = []
    for position, (index, label, role, title) in enumerate(hits):
        end = hits[position + 1][0] if position + 1 < len(hits) else len(text)
        turns.append(
            {
                "role": role,
                "title": title,
                "body": text[index + len(label) : end].strip(),
            }
        )
    return turns


def _stage(
    *,
    stage_id: str,
    phase: str,
    role: str,
    title: str,
    body: str,
    action: str | None = None,
    rating: str | None = None,
) -> dict:
    event = {
        "id": stage_id,
        "phase": phase,
        "role": role,
        "title": title,
        "body": body,
        "status": "complete",
    }
    if action is not None:
        event["action"] = action
    if rating is not None:
        event["rating"] = rating
    return event


def decision_event(body: str, rating: str | None) -> dict:
    shown = rating or "REVIEW"
    return _stage(
        stage_id="decision",
        phase="decision",
        role="portfolio",
        title="Portfolio decision",
        body=body,
        action=paper_action(shown),
        rating=shown,
    )


def _changed_turns(previous: str, current: str, markers: tuple[tuple[str, str, str], ...], prefix: str) -> list[dict]:
    old = split_marked(previous, markers)
    new = split_marked(current, markers)
    events = []
    for index, turn in enumerate(new):
        if index < len(old) and old[index]["body"] == turn["body"] and old[index]["role"] == turn["role"]:
            continue
        events.append(
            _stage(
                stage_id=f"{prefix}-{index}",
                phase=prefix if prefix == "debate" else "risk",
                role=turn["role"],
                title=turn["title"],
                body=turn["body"],
            )
        )
    return events


def diff_chunk(previous: dict, chunk: dict | None, *, rating: str | None = None) -> list[dict]:
    """Events for fields that are new or whose text changed."""

    if not chunk:
        return []
    events: list[dict] = []
    for field, role, title in REPORTS:
        body = chunk.get(field)
        if not isinstance(body, str) or not body.strip():
            continue
        if body == previous.get(field):
            continue
        events.append(
            _stage(stage_id=role, phase="analyst", role=role, title=title, body=body.strip())
        )

    debate = chunk.get("investment_debate_state")
    if isinstance(debate, dict):
        prior = previous.get("investment_debate_state")
        prior_history = prior.get("history", "") if isinstance(prior, dict) else ""
        events.extend(_changed_turns(prior_history, debate.get("history", ""), DEBATE_MARKERS, "debate"))

    plan = chunk.get("investment_plan")
    if isinstance(plan, str) and plan.strip() and plan != previous.get("investment_plan"):
        events.append(
            _stage(
                stage_id="investment-plan",
                phase="plan",
                role="manager",
                title="Research manager",
                body=plan.strip(),
            )
        )

    trader = chunk.get("trader_investment_plan")
    if isinstance(trader, str) and trader.strip() and trader != previous.get("trader_investment_plan"):
        events.append(
            _stage(stage_id="trader", phase="trader", role="trader", title="Trader", body=trader.strip())
        )

    risk = chunk.get("risk_debate_state")
    if isinstance(risk, dict):
        prior = previous.get("risk_debate_state")
        prior_history = prior.get("history", "") if isinstance(prior, dict) else ""
        events.extend(_changed_turns(prior_history, risk.get("history", ""), RISK_MARKERS, "risk"))

    decision = chunk.get("final_trade_decision")
    prior_decision = previous.get("final_trade_decision")
    rating_changed = chunk.get("final_rating") and chunk.get("final_rating") != previous.get("final_rating")
    if isinstance(decision, str) and decision.strip() and (decision != prior_decision or rating_changed):
        events.append(decision_event(decision.strip(), rating))
    return events


def absorb(state: dict, chunk: dict | None) -> None:
    """Fold a stream chunk into the accumulated run state."""

    if not chunk:
        return
    for key, value in chunk.items():
        if key in _SKIP_KEYS or value in (None, "", [], {}):
            continue
        state[key] = value
