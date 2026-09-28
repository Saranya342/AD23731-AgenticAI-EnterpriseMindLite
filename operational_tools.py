"""
Operational diagnostic tools for EnterpriseMind-Lite.

These tools are read-only.

Important:
For now, these are safe demo tools.
They do NOT perform real production infrastructure changes.
"""


# ============================================================
# SERVICE HEALTH TOOL
# ============================================================

def check_service_health(service_name: str) -> dict:
    """
    Demo service health check.

    Replace this later with a real API/monitoring integration
    if you have one.
    """

    demo_status = {
        "Payment Gateway": {
            "status": "degraded",
            "response_time_ms": 2400,
            "message": (
                "Payment Gateway is responding slowly "
                "and some requests are timing out."
            ),
        },

        "Order Management": {
            "status": "degraded",
            "response_time_ms": 1800,
            "message": (
                "Order Management is experiencing "
                "processing delays."
            ),
        },

        "Authentication Service": {
            "status": "healthy",
            "response_time_ms": 180,
            "message": (
                "Authentication Service is operating normally."
            ),
        },
    }

    result = demo_status.get(
        service_name,
        {
            "status": "unknown",
            "response_time_ms": None,
            "message": (
                "No health information is configured "
                f"for {service_name}."
            ),
        },
    )

    return {
        "tool": "check_service_health",
        "service": service_name,
        "source": "demo",
        **result,
    }


# ============================================================
# DATABASE CONNECTIVITY TOOL
# ============================================================

def check_database_connectivity(service_name: str) -> dict:
    """
    Demo database connectivity check.
    """

    demo_status = {
        "Payment Gateway": {
            "connected": True,
            "latency_ms": 95,
            "message": (
                "Database connection is available."
            ),
        },

        "Order Management": {
            "connected": True,
            "latency_ms": 120,
            "message": (
                "Database connection is available "
                "but slightly delayed."
            ),
        },

        "Authentication Service": {
            "connected": True,
            "latency_ms": 60,
            "message": (
                "Database connection is healthy."
            ),
        },
    }

    result = demo_status.get(
        service_name,
        {
            "connected": None,
            "latency_ms": None,
            "message": (
                "No database connectivity information "
                f"is configured for {service_name}."
            ),
        },
    )

    return {
        "tool": "check_database_connectivity",
        "service": service_name,
        "source": "demo",
        **result,
    }


# ============================================================
# RECENT ERROR LOG TOOL
# ============================================================

def get_recent_error_logs(service_name: str) -> dict:
    """
    Demo recent error log retrieval.
    """

    demo_logs = {
        "Payment Gateway": [
            {
                "level": "ERROR",
                "message": (
                    "Payment transaction timeout "
                    "while contacting payment processor."
                ),
            },
            {
                "level": "ERROR",
                "message": (
                    "Checkout request exceeded "
                    "configured timeout threshold."
                ),
            },
        ],

        "Order Management": [
            {
                "level": "ERROR",
                "message": (
                    "Order processing queue delay detected."
                ),
            },
        ],

        "Authentication Service": [],
    }

    logs = demo_logs.get(
        service_name,
        []
    )

    return {
        "tool": "get_recent_error_logs",
        "service": service_name,
        "source": "demo",
        "error_count": len(logs),
        "logs": logs,
    }


# ============================================================
# RUN ALL DIAGNOSTIC TOOLS
# ============================================================

def run_diagnostic_tools(service_name: str) -> list:
    """
    Run all safe diagnostic tools for a service.
    """

    print()
    print(
        f"[TOOLS] Running diagnostics for: "
        f"{service_name}"
    )

    results = []

    health_result = check_service_health(
        service_name
    )

    print(
        "[TOOLS] Service health:",
        health_result["status"]
    )

    results.append(
        health_result
    )

    database_result = check_database_connectivity(
        service_name
    )

    print(
        "[TOOLS] Database connected:",
        database_result["connected"]
    )

    results.append(
        database_result
    )

    log_result = get_recent_error_logs(
        service_name
    )

    print(
        "[TOOLS] Recent errors:",
        log_result["error_count"]
    )

    results.append(
        log_result
    )

    return results


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    import json

    service = "Payment Gateway"

    tool_results = run_diagnostic_tools(
        service
    )

    print()
    print("=" * 60)
    print("TOOL RESULTS")
    print("=" * 60)

    print(
        json.dumps(
            tool_results,
            indent=2
        )
    )