package com.bitora.android.operation

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
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

data class LogisticsResult(val decision: AccessDecision, val reasonCode: String, val title: String, val detail: String)

@Composable
fun LogisticsPanel(identity: PairedDeviceIdentity?, snapshot: BitoraDeviceSnapshot, onSnapshot: (BitoraDeviceSnapshot) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { A2LocalStore(context) }
    var result by remember { mutableStateOf<LogisticsResult?>(null) }
    LaunchedEffect(result) { if (result != null) { delay(3000); result = null } }
    BitoraCard(Modifier.fillMaxWidth()) {
        Text("LOGISTICS", fontWeight = FontWeight.SemiBold)
        Text("Vehicle permits + controlled entry + offline", color = BitoraColors.Offline)
        Spacer(Modifier.height(12.dp))
        Box {
            CameraQrScanner(enabled = identity != null && result == null) { qr -> scope.launch {
                val active = identity
                val r = if (active == null) logisticsDeny("DEVICE_NOT_AUTHORIZED", "Dispositivo no pareado") else persistLogistics(active, store, snapshot, qr)
                result = r; feedback(context, r.decision); syncOperationQueue(active, store)
                onSnapshot(snapshot.copy(queuePending = store.countPending()))
            } }
            result?.let { LogisticsOverlay(it) }
        }
        if (BuildConfig.DEV_TOOLS_ENABLED) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            BitoraSecondaryButton("TEST VEHICLE", Modifier.weight(1f)) { scope.launch {
                val active = identity ?: return@launch
                result = persistLogistics(active, store, snapshot, "BITORA:A7:VALID"); result?.let { feedback(context, it.decision) }
                syncOperationQueue(active, store); onSnapshot(snapshot.copy(queuePending = store.countPending()))
            } }
            BitoraSecondaryButton("TEST DENY", Modifier.weight(1f)) { scope.launch {
                val active = identity ?: return@launch
                result = persistLogistics(active, store, snapshot, "BITORA:A7:DENY"); result?.let { feedback(context, it.decision) }
                syncOperationQueue(active, store); onSnapshot(snapshot.copy(queuePending = store.countPending()))
            } }
        }
    }
}

@Composable private fun LogisticsOverlay(result: LogisticsResult) {
    val color = if (result.decision == AccessDecision.ALLOW) BitoraColors.Success else BitoraColors.Error
    Column(Modifier.fillMaxWidth().heightIn(min = 260.dp).background(color).padding(24.dp), verticalArrangement = Arrangement.Center) {
        Text(result.title, color = Color.White, style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text(result.reasonCode, color = Color.White, style = MaterialTheme.typography.titleMedium)
        Text(result.detail, color = Color.White.copy(alpha = .9f))
    }
}

private suspend fun persistLogistics(identity: PairedDeviceIdentity, store: A2LocalStore, snapshot: BitoraDeviceSnapshot, qr: String): LogisticsResult {
    val ds = store.loadActiveDataset(); val ref = sha256(qr); val duplicate = store.operationState("logistics", ref) == "ENTERED"
    val result = evaluateLogistics(identity, ds?.payloadJson, ds?.organizationId, ds?.eventId, ds?.expiresAtEpochSeconds, qr, duplicate)
    if (result.decision == AccessDecision.ALLOW) store.setOperationState("logistics", ref, "ENTERED")
    val now = Instant.now().toString()
    store.enqueue(LocalQueueItem(operationId = UUID.randomUUID().toString(), idempotencyKey = "${identity.eventId}:VEHICLE_ENTRY:$ref",
        correlationId = UUID.randomUUID().toString(), operationType = "VEHICLE_ACCESS",
        payloadJson = JSONObject().put("event_id", identity.eventId).put("device_id", identity.deviceId).put("vehicle_ref", ref)
            .put("checkpoint", "logistics-main").put("decision", result.decision.name).put("reason_code", result.reasonCode)
            .put("device_timestamp", now).put("dataset_revision", snapshot.dataset.revision ?: store.activeRevision()).toString(),
        occurredAt = now, queuedAt = now, sequence = System.currentTimeMillis()))
    return result
}

internal fun evaluateLogistics(identity: PairedDeviceIdentity, payloadJson: String?, org: Long?, event: Long?, expires: Long?, qr: String, duplicate: Boolean, now: Long = Instant.now().epochSecond): LogisticsResult {
    if (!qr.startsWith("BITORA:")) return logisticsDeny("INVALID_QR", "QR no BITORA")
    if (payloadJson == null) return logisticsDeny("DATASET_UNAVAILABLE", "Dataset no disponible")
    if (org != identity.organizationId || event != identity.eventId) return logisticsDeny("WRONG_EVENT", "Evento incorrecto")
    if ((expires ?: 0) <= now) return logisticsDeny("DATASET_EXPIRED", "Dataset vencido")
    val caps = identity.capabilities.map { it.trim().uppercase() }.toSet()
    if (!caps.containsAll(setOf("VALIDATE_ACCESS", "SCAN_QR")) || identity.profile.trim().uppercase() != "LOGISTICS" || identity.scope.trim().uppercase() != "EVENT:${identity.eventId}:LOGISTICS") return logisticsDeny("DEVICE_NOT_AUTHORIZED", "Perfil, capability o scope no autorizado")
    val payload = JSONObject(payloadJson)
    if (payload.optJSONObject("device")?.optString("profile").orEmpty().uppercase() != "LOGISTICS") return logisticsDeny("DEVICE_NOT_AUTHORIZED", "Dataset de otro perfil")
    val items = payload.optJSONArray("vehicle_permits") ?: JSONArray()
    val permit = (0 until items.length()).map { items.getJSONObject(it) }.firstOrNull { it.optString("token") == qr } ?: return logisticsDeny("UNKNOWN_VEHICLE", "Permiso no encontrado")
    if (permit.optLong("event_id") != identity.eventId) return logisticsDeny("WRONG_EVENT", "Permiso de otro evento")
    if (permit.optString("status") != "ACTIVE") return logisticsDeny("PERMIT_REVOKED", "Permiso inactivo")
    if (permit.optString("checkpoint") != "logistics-main") return logisticsDeny("WRONG_CHECKPOINT", "Punto logistico incorrecto")
    if (duplicate) return logisticsDeny("ALREADY_ENTERED", "Vehiculo ya registrado")
    return LogisticsResult(AccessDecision.ALLOW, "VEHICLE_ALLOWED", "VEHICULO AUTORIZADO", permit.optString("display_label", "Vehiculo"))
}

private fun logisticsDeny(reason: String, detail: String) = LogisticsResult(AccessDecision.DENY, reason, "VEHICULO DENEGADO", detail)
