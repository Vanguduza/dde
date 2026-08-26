package dev.dde.android.gateway

/**
 * Session reconnect store (Ch.15.1 client half).
 *
 * Persists session id + last event cursor. After [resume], callers MUST
 * re-fetch mission and mission-control by id when [ResumeResult.freshSnapshot]
 * is true or retained events cannot rebuild the UI — never trust stale local
 * projection as authority.
 */
data class SessionCursor(
    val sessionId: String,
    val principalId: String,
    val lastEventAt: String?,
)

data class ResumeResult(
    val sessionId: String,
    val freshSnapshot: Boolean,
    val eventCount: Int,
)

interface GatewayTransport {
    suspend fun openSession(
        principalId: String,
        clientType: String,
        scopes: List<String>,
    ): String

    suspend fun resumeSession(
        sessionId: String,
        lastEventAt: String?,
    ): ResumeResult

    suspend fun closeSession(sessionId: String)

    suspend fun readMission(
        sessionId: String,
        principalId: String,
        missionId: String,
    ): Map<String, Any?>

    suspend fun readMissionControl(
        sessionId: String,
        principalId: String,
        missionId: String,
    ): Map<String, Any?>

    suspend fun acceptCommand(
        sessionId: String,
        principalId: String,
        commandId: String,
        idempotencyKey: String,
        targetType: String,
        targetId: String,
        commandType: String,
        parameters: Map<String, Any?>,
    ): Map<String, Any?>
}

class ReconnectCoordinator(
    private val transport: GatewayTransport,
) {
    /**
     * Reconnect: resume, then always re-sync by-id for the active mission.
     * Returns pair (mission, control). Local UI state is discarded.
     */
    suspend fun reconnectAndResync(
        cursor: SessionCursor,
        missionId: String,
    ): Pair<Map<String, Any?>, Map<String, Any?>> {
        val resume = transport.resumeSession(cursor.sessionId, cursor.lastEventAt)
        // Always by-id re-sync: Core may return retained events without a
        // full state snapshot (EDR-0027). freshSnapshot=true is sufficient
        // but not necessary to force re-GET.
        val mission =
            transport.readMission(resume.sessionId, cursor.principalId, missionId)
        val control =
            transport.readMissionControl(
                resume.sessionId,
                cursor.principalId,
                missionId,
            )
        return mission to control
    }
}
