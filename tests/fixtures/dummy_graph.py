"""DUMMY code graph that matches the dummy TDDs, served through the Neo4j query interface.

Not real data and not part of the product. `dummy_run_query` has the same shape as the function
`Neo4jGraphProvider` expects, so the Neo4j provider code path runs end to end without a database.
It recognises the two placeholder queries by their text and answers them from the edge list below.
"""

from collections import deque
from collections.abc import Mapping, Sequence

from impact_agent.providers.neo4j_provider import FIND_CHANGED_QUERY, IMPACT_QUERY

MAX_DEPTH = 4

PROFILE_VIEW = "src/profile/form/view.tsx"
ATS_VIEW = (
    "src/common/accounts/client/components/SettingsForm/sections/AtsIntegrationSection/view.tsx"
)

# id -> (kind, name, service, file)
NODES: dict[str, tuple[str, str, str | None, str | None]] = {
    # Dummy TDD 01 / 02: profile form
    "ui.handleNameBlur": ("function", "handleNameBlur", "ui", PROFILE_VIEW),
    "ui.ProfileForm": ("class", "ProfileForm", "ui", "src/profile/form/index.tsx"),
    "ui.ProfilePage": ("class", "ProfilePage", "ui", "src/profile/page.tsx"),
    "ui.profile_blur_test": (
        "test",
        "handleNameBlur blur test",
        "ui",
        "src/profile/form/view.test.tsx",
    ),
    "accounts.ProfileMutation": (
        "api",
        "updateProfile",
        "accounts-service",
        "src/main/resources/graphql/profile.graphqls",
    ),
    # Sample TDD: ATS integration settings
    "ui.handleCcEmailAddressesBlur": ("function", "handleCcEmailAddressesBlur", "ui", ATS_VIEW),
    "ui.AtsIntegrationSectionView": ("method", "AtsIntegrationSectionView", "ui", ATS_VIEW),
    "ui.SettingsForm": (
        "class",
        "SettingsForm",
        "ui",
        "src/common/accounts/client/components/SettingsForm/index.tsx",
    ),
    "ui.ats_blur_test": (
        "test",
        "ATS CC email blur test",
        "ui",
        ATS_VIEW.replace("view.tsx", "view.test.tsx"),
    ),
    "accounts.SettingsMutation": (
        "api",
        "updateSettings",
        "accounts-service",
        "src/main/resources/graphql/settings.graphqls",
    ),
    # An unrelated node, to prove the graph only returns what depends on the change
    "orders.formatReceipt": (
        "function",
        "formatReceipt",
        "orders-api",
        "src/main/kotlin/orders/ReceiptFormatter.kt",
    ),
}

# (dependent, depends_on, relation): "dependent" breaks or changes if "depends_on" changes.
EDGES: list[tuple[str, str, str]] = [
    ("ui.ProfileForm", "ui.handleNameBlur", "CALLS"),
    ("ui.ProfilePage", "ui.ProfileForm", "CALLS"),
    ("ui.profile_blur_test", "ui.handleNameBlur", "TESTS"),
    ("accounts.ProfileMutation", "ui.ProfilePage", "READS"),
    ("ui.AtsIntegrationSectionView", "ui.handleCcEmailAddressesBlur", "CALLS"),
    ("ui.SettingsForm", "ui.AtsIntegrationSectionView", "CALLS"),
    ("ui.ats_blur_test", "ui.handleCcEmailAddressesBlur", "TESTS"),
    ("accounts.SettingsMutation", "ui.SettingsForm", "READS"),
]


def _find(file: object, symbol: object) -> str | None:
    for node_id, (_, name, _, location) in NODES.items():
        if name == symbol and location == file:
            return node_id
    return None


def _impact(start: str) -> list[dict[str, object]]:
    """Breadth-first walk over dependents, shortest depth first, up to MAX_DEPTH."""
    seen = {start}
    queue = deque([(start, 0)])
    rows: list[dict[str, object]] = []
    while queue:
        current, depth = queue.popleft()
        if depth == MAX_DEPTH:
            continue
        for dependent, target, relation in EDGES:
            if target != current or dependent in seen:
                continue
            seen.add(dependent)
            kind, name, service, location = NODES[dependent]
            rows.append(
                {
                    "id": dependent,
                    "kind": kind,
                    "name": name,
                    "service": service,
                    "location": location,
                    "depth": depth + 1,
                    "relation": relation,
                }
            )
            queue.append((dependent, depth + 1))
    return rows


def dummy_run_query(query: str, params: Mapping[str, object]) -> Sequence[Mapping[str, object]]:
    start = _find(params.get("file"), params.get("symbol"))
    if query == FIND_CHANGED_QUERY:
        return [{"id": start}] if start else []
    if query == IMPACT_QUERY:
        return _impact(start) if start else []
    raise ValueError("dummy_run_query only answers the two Neo4jGraphProvider queries")
