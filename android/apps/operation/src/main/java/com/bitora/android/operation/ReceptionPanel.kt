package com.bitora.android.operation

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.bitora.android.foundation.model.BitoraCapability
import com.bitora.android.foundation.model.BitoraDeviceSnapshot
import com.bitora.android.foundation.network.PairedDeviceIdentity
import com.bitora.android.foundation.persistence.A2LocalStore
import com.bitora.android.foundation.persistence.LocalQueueItem
import com.bitora.android.foundation.theme.BitoraColors
import com.bitora.android.foundation.ui.BitoraCard
import com.bitora.android.foundation.ui.BitoraSecondaryButton
import java.time.Instant
import java.util.UUID
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

data class ReceptionResult(
    val decision: AccessDecision,
    val reasonCode: String,
    val title: String,
    val detail: String,
)

@Composable
fun ReceptionPanel(
    identity: PairedDeviceIdentity?,
    snapshot: BitoraDeviceSnapshot,
    onSnapshot: (BitoraDeviceSnapshot) -> Unit,
    expectedProfile: String = "RECEPTION",
    title: String = "RECEPTION",
    subtitle: String = "Participant resolution + check-in",
    validToken: String = "BITORA:A4:VALID",
    denyToken: String = "BITORA:A4:DENY",
    operationType: String = "PARTICIPANT_CHECK_IN",
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { A2LocalStore(context) }
    var result by remember { mutableStateOf<ReceptionResult?>(null) }

    LaunchedEffect(result) {
        if (result != null) {
            delay(1800)
            result = null
        }
    }

    BitoraCard(Modifier.fillMaxWidth()) {
        Text(title, fontWeight = FontWeight.SemiBold)
        Text(subtitle, color = BitoraColors.Offline)
        Spacer(Modifier.height(12.dp))
        Box {
            CameraQrScanner(enabled = identity != null && result == null) { qr ->
                scope.launch {
                    val activeIdentity = identity
                    val receptionResult = if (activeIdentity == null) {
                        ReceptionResult(AccessDecision.DENY, "DEVICE_NOT_AUTHORIZED", "CHECK-IN DENEGADO", "Dispositivo no pareado")
                    } else {
                        evaluateAndPersistReception(context, activeIdentity, store, snapshot, qr, expectedProfile, operationType)
                    }
                    result = receptionResult
                    feedback(context, receptionResult.decision)
                    syncOperationQueue(activeIdentity, store)
                    onSnapshot(snapshot.copy(queuePending = store.countPending()))
                }
            }
            result?.let { ReceptionResultOverlay(it) }
        }
        if (BuildConfig.DEV_TOOLS_ENABLED) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            BitoraSecondaryButton("TEST CHECK-IN", Modifier.weight(1f)) {
                scope.launch {
                    val activeIdentity = identity ?: return@launch
                    result = evaluateAndPersistReception(context, activeIdentity, store, snapshot, validToken, expectedProfile, operationType)
                    result?.let { feedback(context, it.decision) }
                    syncOperationQueue(activeIdentity, store)
                    onSnapshot(snapshot.copy(queuePending = store.countPending()))
                }
            }
            BitoraSecondaryButton("TEST DENY", Modifier.weight(1f)) {
                scope.launch {
                    val activeIdentity = identity ?: return@launch
                    result = evaluateAndPersistReception(context, activeIdentity, store, snapshot, denyToken, expectedProfile, operationType)
                    result?.let { feedback(context, it.decision) }
                    syncOperationQueue(activeIdentity, store)
                    onSnapshot(snapshot.copy(queuePending = store.countPending()))
                }
            }
        }
    }
}

@Composable
private fun ReceptionResultOverlay(result: ReceptionResult) {
    val color = if (result.decision == AccessDecision.ALLOW) BitoraColors.Success else BitoraColors.Error
    Column(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 260.dp)
            .background(color)
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(result.title, color = Color.White, style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text(result.reasonCode, color = Color.White, style = MaterialTheme.typography.titleMedium)
        Text(result.detail, color = Color.White.copy(alpha = 0.9f))
    }
}

private suspend fun evaluateAndPersistReception(
    context: Context,
    identity: PairedDeviceIdentity,
    store: A2LocalStore,
    snapshot: BitoraDeviceSnapshot,
    qr: String,
    expectedProfile: String = "RECEPTION",
    operationType: String = "PARTICIPANT_CHECK_IN",
): ReceptionResult {
    val dataset = store.loadActiveDataset()
    val tokenHash = sha256(qr)
    val namespace = expectedProfile.lowercase()
    val alreadyCheckedIn = store.operationState(namespace, tokenHash) == "CHECKED_IN"
    val result = evaluateReception(identity, dataset?.payloadJson, dataset?.organizationId, dataset?.eventId, dataset?.expiresAtEpochSeconds, qr, alreadyCheckedIn, expectedProfile = expectedProfile)
    if (result.decision == AccessDecision.ALLOW) {
        store.setOperationState(namespace, tokenHash, "CHECKED_IN")
    }
    val operationId = UUID.randomUUID().toString()
    val payload = JSONObject()
        .put("event_id", identity.eventId)
        .put("device_id", identity.deviceId)
        .put("credential_ref", tokenHash)
        .put("decision", result.decision.name)
        .put("reason_code", result.reasonCode)
        .put("checked_in", result.decision == AccessDecision.ALLOW)
        .put("print_requested", expectedProfile == "SELF_SERVICE" && result.decision == AccessDecision.ALLOW)
        .put("device_timestamp", Instant.now().toString())
        .put("dataset_revision", snapshot.dataset.revision ?: store.activeRevision())
    store.enqueue(
        LocalQueueItem(
            operationId = operationId,
            idempotencyKey = "${identity.eventId}:CHECK_IN:$tokenHash",
            correlationId = UUID.randomUUID().toString(),
            operationType = operationType,
            payloadJson = payload.toString(),
            occurredAt = Instant.now().toString(),
            queuedAt = Instant.now().toString(),
            sequence = System.currentTimeMillis(),
        )
    )
    return result
}

internal fun evaluateReception(
    identity: PairedDeviceIdentity,
    payloadJson: String?,
    datasetOrganizationId: Long?,
    datasetEventId: Long?,
    expiresAtEpochSeconds: Long?,
    qr: String,
    alreadyCheckedIn: Boolean,
    nowEpochSeconds: Long = Instant.now().epochSecond,
    expectedProfile: String = "RECEPTION",
): ReceptionResult {
    if (!qr.startsWith("BITORA:")) return receptionDeny("INVALID_QR", "QR no BITORA")
    if (payloadJson == null) return receptionDeny("DATASET_UNAVAILABLE", "Dataset no disponible")
    if (datasetOrganizationId != identity.organizationId || datasetEventId != identity.eventId) return receptionDeny("WRONG_EVENT", "Evento incorrecto")
    if ((expiresAtEpochSeconds ?: 0) <= nowEpochSeconds) return receptionDeny("DATASET_EXPIRED", "Dataset vencido")
    val capabilities = identity.capabilities.map { it.trim().uppercase() }.toSet()
    val required = setOf(BitoraCapability.CHECK_IN.name, BitoraCapability.SCAN_QR.name, BitoraCapability.VIEW_PARTICIPANT.name)
    if (!capabilities.containsAll(required)) return receptionDeny("DEVICE_NOT_AUTHORIZED", "Capabilities insuficientes")
    if (identity.profile.trim().uppercase() != expectedProfile) return receptionDeny("DEVICE_NOT_AUTHORIZED", "Perfil no autorizado")
    val scope = identity.scope.trim().uppercase().split(':')
    if (scope.size != 3 || scope[0] != "EVENT" || scope[1].toLongOrNull() != identity.eventId || scope[2] != expectedProfile) {
        return receptionDeny("DEVICE_NOT_AUTHORIZED", "Scope no autorizado")
    }
    val payload = JSONObject(payloadJson)
    val deviceProfile = payload.optJSONObject("device")?.optString("profile").orEmpty().uppercase()
    if (deviceProfile != expectedProfile) return receptionDeny("DEVICE_NOT_AUTHORIZED", "Dataset de otro perfil")
    val participants = payload.optJSONArray("participants") ?: JSONArray()
    val participant = (0 until participants.length()).map { participants.getJSONObject(it) }.firstOrNull { it.optString("token") == qr }
        ?: return receptionDeny("UNKNOWN_CREDENTIAL", "Participante no encontrado")
    if (participant.optLong("event_id") != identity.eventId) return receptionDeny("WRONG_EVENT", "Participante de otro evento")
    if (participant.optString("status") != "ACTIVE") return receptionDeny("INACTIVE_ACCREDITATION", "Acreditacion no activa")
    if (participant.optBoolean("checked_in", false) || alreadyCheckedIn) return receptionDeny("ALREADY_CHECKED_IN", "Check-in ya registrado")
    return ReceptionResult(AccessDecision.ALLOW, "CHECKED_IN", "CHECK-IN CONFIRMADO", participant.optString("display_name", "Participante"))
}

private fun receptionDeny(reason: String, detail: String) =
    ReceptionResult(AccessDecision.DENY, reason, "CHECK-IN DENEGADO", detail)
