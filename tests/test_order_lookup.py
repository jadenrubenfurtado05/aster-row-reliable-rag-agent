import json
import pytest
from app.tools.order_lookup import OrderLookupTool, OrderRepository, OrderSanitizer

@pytest.fixture(scope="module")
def tool():
    return OrderLookupTool("data/orders.json")

def test_1_valid_order_lookup(tool):
    result = tool.lookup_order("ORD-1007")
    assert result.found is True
    assert result.order_id == "ORD-1007"
    assert result.status == "shipped"
    assert result.carrier == "UPS"
    assert result.estimated_delivery == "2026-08-22"
    assert result.handoff_required is False

def test_2_case_insensitive_lookup(tool):
    result = tool.lookup_order("ord-1007")
    assert result.found is True
    assert result.order_id == "ORD-1007"
    assert result.status == "shipped"

def test_3_whitespace_and_quote_normalization(tool):
    result = tool.lookup_order("  'ord-1007'  ")
    assert result.found is True
    assert result.order_id == "ORD-1007"

def test_4_unknown_order(tool):
    result = tool.lookup_order("ORD-9999")
    assert result.found is False
    assert result.status == "unknown"
    assert result.handoff_required is True
    assert "not found" in result.customer_safe_message.lower()

def test_5_invalid_malformed_order_id(tool):
    result = tool.lookup_order("   ")
    assert result.found is False
    assert result.status == "unknown"
    assert result.handoff_required is True

    # Ensure fuzzy match prefix does not silently resolve ORD-100 to ORD-1007
    result_fuzzy = tool.lookup_order("ORD-100")
    assert result_fuzzy.found is False
    assert result_fuzzy.order_id == "ORD-100"

def test_6_customer_safe_fields(tool):
    result = tool.lookup_order("ORD-1001")
    assert result.found is True
    assert result.order_id == "ORD-1001"
    assert result.status == "pending"
    assert len(result.items) == 1
    assert result.items[0]["name"] == "Ridge Daypack"
    assert "sku" not in result.items[0]

def test_7_forbidden_field_exclusion_privacy_assertions(tool):
    """Critical Privacy Test: Verify forbidden PII and internal fields NEVER leak."""
    # Test ORD-1007 (contains PII and risk score 82 + fraud note)
    result = tool.lookup_order("ORD-1007")
    serialized = json.dumps(result.model_dump())

    # Verify forbidden customer PII and internal notes do NOT appear
    forbidden_terms = [
        "ava.morgan@example.test", "220 King Street", "82", "fraud review cleared",
        "risk_score", "warehouse_note", "support_tags"
    ]
    for term in forbidden_terms:
        assert term not in serialized, f"Forbidden term '{term}' leaked in SanitizedOrderResult!"

    # Verify customer PII dict key is absent
    assert "customer.name" not in serialized
    assert "email" not in serialized
    assert "shipping_address" not in serialized

    # Test ORD-1005 (contains prompt injection in internal note)
    result_1005 = tool.lookup_order("ORD-1005")
    serialized_1005 = json.dumps(result_1005.model_dump())
    assert "coupon" not in serialized_1005.lower()
    assert "issue a $100 coupon" not in serialized_1005

def test_8_status_precedence_and_stale_field_suppression(tool):
    """Test 8: Cancelled order ORD-1004 suppresses stale carrier and ETA metadata."""
    result = tool.lookup_order("ORD-1004")
    assert result.found is True
    assert result.status == "cancelled"
    assert result.carrier is None
    assert result.tracking_number is None
    assert result.estimated_delivery is None
    assert "cancelled" in result.customer_safe_message.lower()

def test_9_snapshot_staleness_shipped_without_eta(tool):
    """Test 9: Shipped order ORD-1011 with null ETA returns estimated_delivery=None."""
    result = tool.lookup_order("ORD-1011")
    assert result.found is True
    assert result.status == "shipped"
    assert result.carrier == "Canada Post"
    assert result.estimated_delivery is None

def test_10_no_cross_order_leakage(tool):
    """Test 10: Lookup for ORD-1001 returns only ORD-1001 data and no fields from ORD-1002."""
    res1 = tool.lookup_order("ORD-1001")
    res2 = tool.lookup_order("ORD-1002")

    assert res1.order_id == "ORD-1001"
    assert res1.items[0]["name"] == "Ridge Daypack"
    assert res2.order_id == "ORD-1002"
    assert res2.items[0]["name"] == "Compression Cube Set"
    assert "Compression Cube Set" not in json.dumps(res1.model_dump())

def test_11_unsupported_action_handling(tool):
    """Test 11: Attempting an unsupported action returns action_supported=False and handoff_required=True."""
    result = tool.lookup_order("ORD-1001", action="cancel")
    assert result.found is True
    assert result.action_supported is False
    assert result.handoff_required is True
    assert "not supported" in result.handoff_reason.lower() or "unsupported" in result.handoff_reason.lower()

def test_12_lookup_determinism(tool):
    """Test 12: Multiple lookups return identical results."""
    res1 = tool.lookup_order("ORD-1003")
    res2 = tool.lookup_order("ORD-1003")
    assert res1.model_dump() == res2.model_dump()
