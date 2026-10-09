import argparse
import asyncio
import json

import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from ontolens.config import env_value


async def run(url):
    token = env_value("MCP_TOKEN", "")
    headers = {"Authorization": "Bearer " + token} if token else {}
    async with httpx.AsyncClient(headers=headers, trust_env=False, timeout=30) as client, \
            streamable_http_client(url, http_client=client) as (reader, writer, session_identifier):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            available = await session.list_tools()
            assert {tool.name for tool in available.tools} == {
                "evidence_lookup", "graph_query", "asset_recognition", "candidate_suggestions", "evidence_rerank_jev", "decision_check", "candidate_review"}
            result = await session.call_tool("decision_check", {"request": {
                "request_id": "MCP-SMOKE", "requester_id": "stu03", "lot_id": "lot_eth",
                "destination_cabinet_id": "cab_flam", "quantity": 100, "unit": "mL",
                "as_of": "2026-09-23", "version_id": "demo-initial",
            }})
            assert not result.isError
            payload = json.loads(result.content[0].text)
            assert payload["decision"]["reason_code"] == "SESSION_INCOMPATIBLE"
            reranked = await session.call_tool("evidence_rerank_jev", {"query": "stu03 授权", "version_id": "demo-initial", "limit": 5})
            assert not reranked.isError
            rerank_payload = json.loads(reranked.content[0].text)
            assert rerank_payload["status"] == "unavailable"
            lookup = await session.call_tool("evidence_lookup", {"query": "stu03", "version_id": "demo-initial"})
            assert not lookup.isError
            lookup_payload = json.loads(lookup.content[0].text)
            source_id = lookup_payload["results"][0]["id"]
            evidence = lookup_payload["results"][0]
            reviewed = await session.call_tool("evidence_rerank_jev", {
                "query": "核对这项合成陈述的来源", "version_id": "demo-initial", "limit": 1,
                "citations": [{"source_id": source_id, "locator": evidence["locator"],
                               "quote": evidence["text"], "sha256": evidence["sha256"]}],
            })
            assert not reviewed.isError
            review_payload = json.loads(reviewed.content[0].text)
            assert review_payload["citation_check"]["status"] == "passed"
            assert review_payload["status"] == "unavailable" and review_payload["request_count"] == 0
            assets = await session.call_tool("asset_recognition", {"source_id": source_id})
            assert not assets.isError
            asset_payload = json.loads(assets.content[0].text)
            assert asset_payload["schema"]["version"] == "ontolens-ontology-1"
            print("MCP SDK smoke: PASS — 7 tools, assets, decision_check, JEV fallback and offline citation check")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765/mcp/")
    asyncio.run(run(parser.parse_args().url))
