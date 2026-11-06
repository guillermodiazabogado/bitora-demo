package com.bitora.android.operation

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

data class LeadResult(val decision: AccessDecision, val reasonCode: String, val title: String, val detail: String)

@Composable
fun LeadRetrievalPanel(identity: PairedDeviceIdentity?, snapshot: BitoraDeviceSnapshot, onSnapshot: (BitoraDeviceSnapshot) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { A2LocalStore(context) }
    var result by remember { mutableStateOf<LeadResult?>(null) }
    LaunchedEffect(result) { if (result != null) { delay(3000); result = null } }

    BitoraCard(Modifier.fillMaxWidth()) {
        Text("LEAD RETRIEVAL", fontWeight = FontWeight.SemiBold)
        Text("Participant scan + consent + offline capture", color = BitoraColors.Offline)
        Spacer(Modifier.height(12.dp))
        Box {
            CameraQrScanner(enabled = identity != null && result == null) { qr ->
                scope.launch {
                    val active = identity
                    val leadResult = if (active == null) leadDeny("DEVICE_NOT_AUTHORIZED", "Dispositivo no pareado")
                    else evaluateAndPersistLead(active, store, snapshot, qr)
                    result = leadResult
                    feedback(context, leadResult.decision)
                    syncOperationQueue(active, store)
                    onSnapshot(snapshot.copy(queuePending = store.countPending()))
                }
            }
            result?.let { LeadResultOverlay(it) }
        }
        if (BuildConfig.DEV_TOOLS_ENABLED) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            BitoraSecondaryButton("TEST LEAD", Modifier.weight(1f)) {
                scope.launch {
                    val active = identity ?: return@launch
                    result = evaluateAndPersistLead(active, store, snapshot, "BITORA:A6:VALID")
                    result?.let { feedback(context, it.decision) }
                    syncOperationQueue(active, store)
                    onSnapshot(snapshot.copy(queuePending = store.countPending()))
                }
            }
            BitoraSecondaryButton("TEST DENY", Modifier.weight(1f)) {
                scope.launch {
                    val active = identity ?: return@launch
                    result = evaluateAndPersistLead(active, store, snapshot, "BITORA:A6:DENY")
                    result?.let { feedback(context, it.decision) }
                    syncOperationQueue(active, store)
                    onSnapshot(snapshot.copy(queuePending = store.countPending()))
                }
            }
        }
    }
}

@Composable
private fun LeadResultOverlay(result: LeadResult) {
    val color = if (result.decision == AccessDecision.ALLOW) BitoraColors.Success else BitoraColors.Error
    Column(Modifier.fillMaxWidth().heightIn(min = 260.dp).background(color).padding(24.dp), verticalArrangement = Arrangement.Center) {
        Text(result.title, color = Color.White, style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text(result.reasonCode, color = Color.White, style = MaterialTheme.typography.titleMedium)
        Text(result.detail, color = Color.White.copy(alpha = 0.9f))
    }
}

private suspend fun evaluateAndPersistLead(identity: PairedDeviceIdentity, store: A2LocalStore, snapshot: BitoraDeviceSnapshot, qr: String): LeadResult {
    val dataset = store.loadActiveDataset()
    val tokenHash = sha256(qr)
    val duplicate = store.operationState("lead_capture", tokenHash) == "CAPTURED"
    val result = evaluateLead(identity, dataset?.payloadJson, dataset?.organizationId, dataset?.eventId, dataset?.expiresAtEpochSeconds, qr, duplicate)
    if (result.decision == AccessDecision.ALLOW) store.setOperationState("lead_capture", tokenHash, "CAPTURED")
    val now = Instant.now().toString()
    store.enqueue(LocalQueueItem(
        operationId = UUID.randomUUID().toString(),
        idempotencyKey = "${identity.eventId}:LEAD:${identity.deviceId}:$tokenHash",
        correlationId = UUID.randomUUID().toString(),
        operationType = "LEAD_CAPTURE",
        payloadJson = JSONObject().put("event_id", identity.eventId).put("device_id", identity.deviceId)
            .put("participant_ref", tokenHash).put("decision", result.decision.name).put("reason_code", result.reasonCode)
            .put("consent_verified", result.decision == AccessDecision.ALLOW).put("device_timestamp", now)
            .put("dataset_revision", snapshot.dataset.revision ?: store.activeRevision()).toString(),
        occurredAt = now,
        queuedAt = now,
        sequence = System.currentTimeMillis(),
    ))
    return result
}

internal fun evaluateLead(identity: PairedDeviceIdentity, payloadJson: String?, datasetOrganizationId: Long?, datasetEventId: Long?, expiresAtEpochSeconds: Long?, qr: String, duplicate: Boolean, nowEpochSeconds: Long = Instant.now().epochSecond): LeadResult {
    if (!qr.startsWith("BITORA:")) return leadDeny("INVALID_QR", "QR no BITORA")
    if (payloadJson == null) return leadDeny("DATASET_UNAVAILABLE", "Dataset no disponible")
    if (datasetOrganizationId != identity.organizationId || datasetEventId != identity.eventId) return leadDeny("WRONG_EVENT", "Evento incorrecto")
    if ((expiresAtEpochSeconds ?: 0) <= nowEpochSeconds) return leadDeny("DATASET_EXPIRED", "Dataset vencido")
    val caps = identity.capabilities.map { it.trim().uppercase() }.toSet()
    if (!caps.containsAll(setOf("SCAN_QR", "VIEW_PARTICIPANT"))) return leadDeny("DEVICE_NOT_AUTHORIZED", "Capabilities insuficientes")
    if (identity.profile.trim().uppercase() != "LEAD_RETRIEVAL") return leadDeny("DEVICE_NOT_AUTHORIZED", "Perfil no autorizado")
    if (identity.scope.trim().uppercase() != "EVENT:${identity.eventId}:LEAD_RETRIEVAL") return leadDeny("DEVICE_NOT_AUTHORIZED", "Scope no autorizado")
    val payload = JSONObject(payloadJson)
    if (payload.optJSONObject("device")?.optString("profile").orEmpty().uppercase() != "LEAD_RETRIEVAL") return leadDeny("DEVICE_NOT_AUTHORIZED", "Dataset de otro perfil")
    val leads = payload.optJSONArray("lead_participants") ?: JSONArray()
    val participant = (0 until leads.length()).map { leads.getJSONObject(it) }.firstOrNull { it.optString("token") == qr }
        ?: return leadDeny("UNKNOWN_CREDENTIAL", "Participante no encontrado")
    if (participant.optLong("event_id") != identity.eventId) return leadDeny("WRONG_EVENT", "Participante de otro evento")
    if (participant.optString("status") != "ACTIVE") return leadDeny("INACTIVE_ACCREDITATION", "Acreditacion no activa")
    if (!participant.optBoolean("lead_consent", false)) return leadDeny("CONSENT_REQUIRED", "Sin consentimiento para compartir datos")
    if (duplicate) return leadDeny("ALREADY_CAPTURED", "Lead ya capturado")
    return LeadResult(AccessDecision.ALLOW, "LEAD_CAPTURED", "LEAD CAPTURADO", participant.optString("display_name", "Participante"))
}

private fun leadDeny(reason: String, detail: String) = LeadResult(AccessDecision.DENY, reason, "LEAD DENEGADO", detail)
