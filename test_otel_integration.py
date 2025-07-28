#!/usr/bin/env python3
"""
Test script for OpenTelemetry integration with Insights Host Inventory.

This script demonstrates and tests the OpenTelemetry instrumentation
setup for host update operations.
"""

import json
import os
import time
from unittest.mock import Mock

# Set environment variables for testing
os.environ.update(
    {
        "OTEL_ENABLED": "true",
        "OTEL_SERVICE_NAME": "insights-host-inventory-test",
        "OTEL_CONSOLE_EXPORTER": "true",
        "OTEL_TRACE_SAMPLE_RATE": "1.0",  # Sample all traces for testing
        "BYPASS_RBAC": "true",
        "BYPASS_TENANT_TRANSLATION": "true",
        "BYPASS_UNLEASH": "true",
    }
)

# Now import the app modules after setting environment
from app.logging import get_logger
from app.otel_config import get_tracer
from app.otel_config import setup_opentelemetry
from app.otel_instrumentation import add_span_attributes
from app.otel_instrumentation import create_child_span
from app.otel_instrumentation import record_host_operation_result
from app.otel_instrumentation import trace_host_operation

logger = get_logger(__name__)


def test_basic_otel_setup():
    """Test basic OpenTelemetry setup and configuration."""
    print("=" * 60)
    print("Testing OpenTelemetry Basic Setup")
    print("=" * 60)

    # Initialize OpenTelemetry
    tracer = setup_opentelemetry()

    if tracer:
        print("✅ OpenTelemetry initialized successfully")
        print("   Service name: insights-host-inventory-test")
        print("   Console exporter enabled")
    else:
        print("❌ OpenTelemetry initialization failed")
        return False

    # Test basic span creation
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("test_span") as span:
        span.set_attribute("test.attribute", "test_value")
        span.add_event("Test event")
        print("✅ Basic span creation and attributes working")

    print()
    return True


def test_host_operation_tracing():
    """Test the host operation tracing decorator."""
    print("=" * 60)
    print("Testing Host Operation Tracing Decorator")
    print("=" * 60)

    @trace_host_operation(
        "test_host_operation",
        extract_host_id=lambda host_data, *args, **kwargs: host_data.get("id"),
        extract_org_id=lambda host_data, *args, **kwargs: host_data.get("org_id"),
        extract_reporter=lambda host_data, *args, **kwargs: host_data.get("reporter"),
    )
    def mock_host_operation(host_data):
        """Mock host operation function."""
        print(f"   Processing host: {host_data.get('id', 'unknown')}")

        # Add some span attributes
        add_span_attributes(
            {
                "host.display_name": host_data.get("display_name"),
                "host.account": host_data.get("account"),
            }
        )

        # Simulate some processing time
        time.sleep(0.1)

        # Record operation result
        result = Mock()
        result.name = "created"
        record_host_operation_result(result, host_data)

        return result

    # Test with sample host data
    test_host_data = {
        "id": "test-host-123",
        "org_id": "test-org-456",
        "reporter": "test-reporter",
        "display_name": "Test Host",
        "account": "test-account",
    }

    try:
        result = mock_host_operation(test_host_data)
        print("✅ Host operation tracing decorator working")
        print(f"   Operation result: {result.name}")
        print()
        return True
    except Exception as e:
        print(f"❌ Host operation tracing failed: {e}")
        print()
        return False


def test_child_spans():
    """Test child span creation."""
    print("=" * 60)
    print("Testing Child Span Creation")
    print("=" * 60)

    tracer = get_tracer(__name__)

    with tracer.start_as_current_span("parent_span") as parent:
        parent.set_attribute("span.type", "parent")
        print("   Created parent span")

        with create_child_span("child_operation") as child:
            child.set_attribute("operation", "child_work")
            print("   Created child span")
            time.sleep(0.05)

        with create_child_span("another_child_operation") as child2:
            child2.set_attribute("operation", "more_child_work")
            print("   Created another child span")
            time.sleep(0.05)

    print("✅ Child span creation working")
    print()
    return True


def test_error_handling():
    """Test error handling in traced operations."""
    print("=" * 60)
    print("Testing Error Handling in Traces")
    print("=" * 60)

    @trace_host_operation("test_error_operation")
    def failing_operation():
        """Function that always fails."""
        raise ValueError("Test error for tracing")

    try:
        failing_operation()
        print("❌ Error handling test failed - no exception raised")
        return False
    except ValueError as e:
        print("✅ Error handling working - exception recorded in span")
        print(f"   Exception: {e}")
        print()
        return True
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_mq_message_simulation():
    """Simulate message queue processing with tracing."""
    print("=" * 60)
    print("Testing Message Queue Processing Simulation")
    print("=" * 60)

    from app.otel_instrumentation import trace_mq_message_processing

    @trace_mq_message_processing("test_message_processing")
    def process_test_message(message_data):
        """Simulate processing a message from the queue."""
        add_span_attributes(
            {
                "messaging.system": "kafka",
                "messaging.topic": "platform.inventory.host-ingress",
                "message.size": len(json.dumps(message_data)),
            }
        )

        # Simulate host processing
        with create_child_span("parse_message"):
            parsed_data = json.loads(json.dumps(message_data))  # Simulate parsing
            time.sleep(0.02)

        with create_child_span("validate_host"):
            # Simulate validation
            if not parsed_data.get("org_id"):
                raise ValueError("Missing org_id")
            time.sleep(0.03)

        with create_child_span("save_to_db"):
            # Simulate database save
            time.sleep(0.05)

        return {"status": "success", "host_id": parsed_data.get("id")}

    test_message = {
        "id": "msg-host-789",
        "org_id": "org-789",
        "reporter": "test-mq-reporter",
        "display_name": "MQ Test Host",
        "canonical_facts": {
            "insights_id": "insights-123",
        },
    }

    try:
        result = process_test_message(test_message)
        print("✅ Message queue processing simulation working")
        print(f"   Result: {result}")
        print()
        return True
    except Exception as e:
        print(f"❌ Message queue processing failed: {e}")
        print()
        return False


def run_all_tests():
    """Run all OpenTelemetry integration tests."""
    print("🚀 Starting OpenTelemetry Integration Tests")
    print("=" * 60)

    tests = [
        test_basic_otel_setup,
        test_host_operation_tracing,
        test_child_spans,
        test_error_handling,
        test_mq_message_simulation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            failed += 1

    print("=" * 60)
    print("🏁 Test Results Summary")
    print("=" * 60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total:  {passed + failed}")

    if failed == 0:
        print("\n🎉 All tests passed! OpenTelemetry integration is working correctly.")
        print("\n📋 To enable OpenTelemetry in production:")
        print("   - Set OTEL_ENABLED=true")
        print("   - Configure OTEL_JAEGER_ENDPOINT or OTEL_OTLP_ENDPOINT")
        print("   - Adjust OTEL_TRACE_SAMPLE_RATE (default: 0.1)")
        print("\n📋 Example environment variables:")
        print("   export OTEL_ENABLED=true")
        print("   export OTEL_SERVICE_NAME=insights-host-inventory")
        print("   export OTEL_JAEGER_ENDPOINT=jaeger-collector:14268")
        print("   export OTEL_TRACE_SAMPLE_RATE=0.1")
        return True
    else:
        print(f"\n❌ {failed} test(s) failed. Please check the configuration.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
