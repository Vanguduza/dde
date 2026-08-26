package dev.dde.android.gateway

/**
 * DDE-053 Gateway /v1 allowlist — must stay identical to
 * interfaces/dashboard/static/gateway.js ALLOWED_PATHS (DDE-052 API parity).
 */
object GatewayAllowlist {
    val ALLOWED_PATHS: List<String> =
        listOf(
            "POST /v1/sessions",
            "POST /v1/sessions/{id}/resume",
            "POST /v1/sessions/{id}/close",
            "POST /v1/commands",
            "GET /v1/missions/{id}",
            "GET /v1/mission-control/{id}",
        )
}
