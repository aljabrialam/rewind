"""tests/contract/test_alternate_endpoint_contract.py — spec 008 FR-008-08.

The one-time Article VIII assessment: is the self-hosted alternate endpoint
reachable and does it return a verdict that passes the SAME schema as the
primary? Green -> the alternate may go on a captured demo run. Skipped when
CRITIC_BASE_URL is unset (NFR-008-02).

Run:  CRITIC_BASE_URL=... CRITIC_MODEL=... pytest tests/contract/test_alternate_endpoint_contract.py -m live -q
"""

import os

import pytest

from rewind.reasoning import validate_verdict, verdict_ids_from_bundle

pytestmark = pytest.mark.live

_BUNDLE = (
    "branch aaaa | exit 0 | elapsed 0.2s\noutput:\nPASS\n---\n"
    "branch bbbb | exit 1 | elapsed 0.3s\noutput:\nAssertionError\n---\n"
)


@pytest.mark.skipif(not (os.environ.get("CRITIC_BASE_URL") and os.environ.get("CRITIC_MODEL")),
                    reason="CRITIC_BASE_URL / CRITIC_MODEL not set")
def test_alternate_reachable_and_conforming():
    from rewind.reasoning import LiveReasoner

    alt = LiveReasoner(
        base_url=os.environ["CRITIC_BASE_URL"],
        model=os.environ["CRITIC_MODEL"],
        api_key=os.environ.get("CRITIC_API_KEY") or os.environ.get("LLM_API_KEY"),
    )
    raw = alt.next_instruction(
        _BUNDLE + '\nReply {"chosen": "<branch id>", "scores": {"aaaa": <n>, "bbbb": <n>}, '
        '"reason": "<cite the evidence>"}.')
    verdict = validate_verdict(raw, verdict_ids_from_bundle(_BUNDLE))   # same schema as the primary
    assert verdict.chosen in ("aaaa", "bbbb")
    assert set(verdict.scores) == {"aaaa", "bbbb"}
