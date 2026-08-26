package dev.dde.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import dev.dde.android.OperatorViewModel

@Composable
fun OperatorScreen(vm: OperatorViewModel = viewModel()) {
    val state by vm.state.collectAsState()
    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("DDE", style = MaterialTheme.typography.headlineMedium)
        Text(
            "Android thin client · Gateway only",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedTextField(
            value = state.gatewayUrl,
            onValueChange = vm::onGatewayUrlChange,
            label = { Text("Gateway base URL") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        OutlinedTextField(
            value = state.principalId,
            onValueChange = vm::onPrincipalIdChange,
            label = { Text("Principal UUID") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        OutlinedTextField(
            value = state.missionId,
            onValueChange = vm::onMissionIdChange,
            label = { Text("Mission UUID") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = vm::connect, enabled = !state.busy) { Text("Open session") }
            OutlinedButton(onClick = vm::loadMission, enabled = state.sessionId != null && !state.busy) {
                Text("Load")
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { vm.control("mission.pause") }, enabled = state.sessionId != null && !state.busy) {
                Text("Pause")
            }
            OutlinedButton(onClick = { vm.control("mission.resume") }, enabled = state.sessionId != null && !state.busy) {
                Text("Resume")
            }
            OutlinedButton(onClick = { vm.control("mission.cancel") }, enabled = state.sessionId != null && !state.busy) {
                Text("Cancel")
            }
            OutlinedButton(onClick = vm::reconnect, enabled = state.sessionId != null && !state.busy) {
                Text("Reconnect")
            }
        }
        Text(state.status, color = MaterialTheme.colorScheme.onSurface)
        Text("Mission", style = MaterialTheme.typography.titleMedium)
        Text(state.missionSummary.ifBlank { "Nothing loaded." })
        Text("Mission control", style = MaterialTheme.typography.titleMedium)
        Text(state.controlSummary.ifBlank { "Nothing loaded." })
        Text(
            "No list endpoint yet — paste a known mission id. Acceptance ≠ completion.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
