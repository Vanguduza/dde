package dev.dde.android.gateway

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class GatewayAllowlistTest {
    @Test
    fun allowlistMatchesDashboardSixPaths() {
        val expected =
            listOf(
                "POST /v1/sessions",
                "POST /v1/sessions/{id}/resume",
                "POST /v1/sessions/{id}/close",
                "POST /v1/commands",
                "GET /v1/missions/{id}",
                "GET /v1/mission-control/{id}",
            )
        assertEquals(expected, GatewayAllowlist.ALLOWED_PATHS)
    }

    @Test
    fun humanScopesIncludeMissionReadAndControl() {
        assertTrue(HumanMissionScopes.ALL.contains("mission.read"))
        assertTrue(HumanMissionScopes.ALL.contains("mission.control"))
    }
}
