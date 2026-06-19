from pathlib import Path

from src.agent import load_agent_tables, local_agent_reply


DATA_DIR = Path(__file__).parents[1] / "data"


def test_policy_comparison_routes_to_policy_evaluation() -> None:
    tables = load_agent_tables(DATA_DIR)
    response = local_agent_reply(
        "Compare the baseline and AI-assisted replenishment policies across stockout rate, service level, and total SCM cost.",
        tables,
        lang="en",
    )

    assert "KPI comparison" in response
    assert "Stockout rate" in response
    assert "Service level" in response
    assert "Total SCM cost" in response
    assert "synthetic offline simulation" in response


def test_reorder_question_returns_ranked_actions() -> None:
    tables = load_agent_tables(DATA_DIR)
    response = local_agent_reply(
        "Rank the SKUs with the highest stockout risk and recommend order quantities.",
        tables,
        lang="en",
    )

    assert "Top reorder priorities" in response
    assert "Recommended order" in response
    assert "Decision logic" in response


def test_transfer_question_is_grounded_in_transfer_table() -> None:
    tables = load_agent_tables(DATA_DIR)
    response = local_agent_reply("Where can store transfers help?", tables, lang="en")

    assert "STORE TRANSFER RECOMMENDATIONS" in response
    assert "->" in response

