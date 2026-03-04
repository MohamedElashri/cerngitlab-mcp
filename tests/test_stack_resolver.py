"""Unit tests for the LHCb stack resolver."""

import pytest
import httpx

from cerngitlab_mcp.stack_resolver import resolve_stack, STACK_API_BASE

@pytest.mark.asyncio
async def test_resolve_stack_success(httpx_mock):
    stack_name = "sim11"
    url = f"{STACK_API_BASE}/lhcb-{stack_name}/latest/"
    
    httpx_mock.add_response(
        url=url,
        json={
            "builds": {
                "x86_64_v2-el9-gcc13-opt": {
                    "Boole": {},
                    "DD4hepDDG4": {},
                }
            }
        }
    )
    
    result = await resolve_stack(stack_name)
    assert result == {"Boole": "sim11", "DD4hepDDG4": "sim11"}

@pytest.mark.asyncio
async def test_resolve_stack_empty_name():
    result = await resolve_stack("")
    assert result == {}

@pytest.mark.asyncio
async def test_resolve_stack_api_error(httpx_mock, caplog):
    stack_name = "sim11"
    url = f"{STACK_API_BASE}/lhcb-{stack_name}/latest/"
    
    httpx_mock.add_response(url=url, status_code=500)
    
    result = await resolve_stack(stack_name)
    assert result == {}
    assert "Failed to resolve stack 'sim11'" in caplog.text

@pytest.mark.asyncio
async def test_resolve_stack_no_builds(httpx_mock):
    stack_name = "sim11"
    url = f"{STACK_API_BASE}/lhcb-{stack_name}/latest/"
    
    httpx_mock.add_response(url=url, json={"builds": {}})
    
    result = await resolve_stack(stack_name)
    assert result == {}
