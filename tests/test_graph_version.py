import hashlib
from pathlib import Path

from peiwu.workspace import Workspace, encode, timestamp


ROOT = Path(__file__).resolve().parents[1]


def test_graph_labels_the_rule_card_in_the_selected_snapshot(tmp_path):
    workspace = Workspace(ROOT, tmp_path / "graph.sqlite3")
    original = workspace.version("demo-initial")
    snapshot = original["snapshot"]
    snapshot["rules"] = snapshot["rules"].replace("version: v2", "version: v-test")
    encoded = encode(snapshot)
    with workspace.connect(write=True) as connection:
        connection.execute(
            "INSERT INTO versions VALUES(?,?,?,?,?,?)",
            (
                "version-under-test",
                original["id"],
                encoded,
                hashlib.sha256(encoded.encode()).hexdigest(),
                "规则标签测试",
                timestamp(),
            ),
        )

    graph = workspace.graph("stu01", "lot_eth", "cab_flam", "version-under-test")
    rule_edge = next(edge for edge in graph["edges"] if edge["relation"] == "规则版本")

    assert rule_edge["target"] == "v-test"
