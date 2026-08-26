package dev.dde.android.gateway

/**
 * Expected HTTP shapes for the Android Gateway client (DDE-053).
 * Concrete OkHttp/Ktor wiring lands with the Android CI job (EDR-0029);
 * behaviour is pinned by tests/unit/test_android_gateway_reconnect.py.
 */
data class OpenSessionRequest(
    val principalId: String,
    val clientType: String = "human",
    val scopes: List<String>,
    val subscriptions: List<String> = listOf("mission"),
    val protocolVersion: String = "1",
)

data class CommandRequest(
    val commandId: String,
    val idempotencyKey: String,
    val principalId: String,
    val clientSessionId: String,
    val targetType: String,
    val targetId: String,
    val commandType: String,
    val parameters: Map<String, Any?> = emptyMap(),
    val protocolVersion: String = "1",
)

/**
 * Human baseline scopes used by the web dashboard (API parity).
 * Do not switch to client_type=device — device baseline has no mission.*.
 */
object HumanMissionScopes {
    val ALL: List<String> =
        listOf(
            "mission.read",
            "mission.create",
            "mission.control",
            "approval.read",
            "approval.decide",
            "approval.request",
            "credential.capture",
        )
}
