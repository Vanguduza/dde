package dev.dde.android

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import dev.dde.android.gateway.GatewayApiException
import dev.dde.android.gateway.HumanMissionScopes
import dev.dde.android.gateway.OkHttpGatewayTransport
import dev.dde.android.gateway.ReconnectCoordinator
import dev.dde.android.gateway.SessionCursor
import dev.dde.android.gateway.newIdempotencyKey
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class OperatorUiState(
    val gatewayUrl: String = "http://10.0.2.2:8000",
    val principalId: String = "",
    val missionId: String = "",
    val sessionId: String? = null,
    val lastEventAt: String? = null,
    val status: String = "No session.",
    val missionSummary: String = "",
    val controlSummary: String = "",
    val busy: Boolean = false,
)

class OperatorViewModel(
    application: Application,
) : AndroidViewModel(application) {
    private val _state = MutableStateFlow(OperatorUiState())
    val state: StateFlow<OperatorUiState> = _state.asStateFlow()

    private var transport: OkHttpGatewayTransport? = null

    fun onGatewayUrlChange(value: String) = _state.update { it.copy(gatewayUrl = value) }

    fun onPrincipalIdChange(value: String) = _state.update { it.copy(principalId = value) }

    fun onMissionIdChange(value: String) = _state.update { it.copy(missionId = value) }

    fun connect() {
        viewModelScope.launch {
            runOp("Opening session") {
                val t = OkHttpGatewayTransport(_state.value.gatewayUrl)
                transport = t
                val sessionId =
                    t.openSession(
                        principalId = _state.value.principalId.trim(),
                        clientType = "human",
                        scopes = HumanMissionScopes.ALL,
                    )
                _state.update {
                    it.copy(
                        sessionId = sessionId,
                        status = "Session $sessionId",
                        lastEventAt = null,
                    )
                }
            }
        }
    }

    fun loadMission() {
        viewModelScope.launch {
            runOp("Loading mission") {
                val t = requireTransport()
                val s = requireSession()
                val missionId = _state.value.missionId.trim()
                val principalId = _state.value.principalId.trim()
                val mission = t.readMission(s, principalId, missionId)
                val control = t.readMissionControl(s, principalId, missionId)
                applyMission(mission, control)
            }
        }
    }

    fun control(commandType: String) {
        viewModelScope.launch {
            runOp("Command $commandType") {
                val t = requireTransport()
                val s = requireSession()
                val missionId = _state.value.missionId.trim()
                val acceptance =
                    t.acceptCommand(
                        sessionId = s,
                        principalId = _state.value.principalId.trim(),
                        commandId = newIdempotencyKey("cmd"),
                        idempotencyKey = newIdempotencyKey(commandType),
                        targetType = "mission",
                        targetId = missionId,
                        commandType = commandType,
                        parameters = emptyMap(),
                    )
                _state.update {
                    it.copy(
                        status =
                            "Accepted $commandType " +
                                "(command_id=${acceptance["command_id"]}, " +
                                "status=${acceptance["status"]}). Reloading…",
                    )
                }
                val mission =
                    t.readMission(s, _state.value.principalId.trim(), missionId)
                val control =
                    t.readMissionControl(s, _state.value.principalId.trim(), missionId)
                applyMission(mission, control)
            }
        }
    }

    fun reconnect() {
        viewModelScope.launch {
            runOp("Reconnect") {
                val t = requireTransport()
                val s = requireSession()
                val missionId = _state.value.missionId.trim()
                val coordinator = ReconnectCoordinator(t)
                val (mission, control) =
                    coordinator.reconnectAndResync(
                        SessionCursor(
                            sessionId = s,
                            principalId = _state.value.principalId.trim(),
                            lastEventAt = _state.value.lastEventAt,
                        ),
                        missionId = missionId,
                    )
                applyMission(mission, control)
                _state.update { it.copy(status = "Reconnected; re-synced by id.") }
            }
        }
    }

    private fun applyMission(
        mission: Map<String, Any?>,
        control: Map<String, Any?>,
    ) {
        _state.update {
            it.copy(
                missionSummary =
                    listOf(
                        "slug=${mission["slug"]}",
                        "status=${mission["status"]}",
                        "mission_id=${mission["mission_id"]}",
                        "updated_at=${mission["updated_at"]}",
                    ).joinToString("\n"),
                controlSummary =
                    listOf(
                        "status=${control["status"]}",
                        "task_total=${control["task_total"]}",
                        "tasks_completed=${control["tasks_completed"]}",
                        "open_attention_items=${control["open_attention_items"]}",
                    ).joinToString("\n"),
                status = "Loaded ${mission["slug"]} (${mission["status"]}).",
            )
        }
    }

    private fun requireTransport(): OkHttpGatewayTransport =
        transport ?: error("Open a session first")

    private fun requireSession(): String =
        _state.value.sessionId ?: error("Open a session first")

    private suspend fun runOp(
        label: String,
        block: suspend () -> Unit,
    ) {
        _state.update { it.copy(busy = true, status = "$label…") }
        try {
            block()
        } catch (e: GatewayApiException) {
            _state.update { it.copy(status = "${e.errorFamily}: ${e.message}") }
        } catch (e: Exception) {
            _state.update { it.copy(status = e.message ?: e.toString()) }
        } finally {
            _state.update { it.copy(busy = false) }
        }
    }
}
