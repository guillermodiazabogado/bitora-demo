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

data class ServiceResult(
    val decision: AccessDecision,
    val reasonCode: String,
    val title: String,
    val detail: String,
)

@Composable
fun ServicePanel(
    identity: PairedDeviceIdentity?,
    snapshot: BitoraDeviceSnapshot,
    onSnapshot: (BitoraDeviceSnapshot) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { A2LocalStore(context) }
    var result by remember { mutableStateOf<ServiceResult?>(null) }

    LaunchedEffect(result) {
        if (result != null) {
            delay(3000)
            result = null
        }
    }

    BitoraCard(Modifier.fillMaxWidth()) {
        Text("SERVICE", fontWeight = FontWeight.SemiBold)
        Text("Coffee point / entitlement consumption", color = BitoraColors.Offline)
        Spacer(Modifier.height(12.dp))
        Box {
            CameraQrScanner(enabled = identity != null && result == null) { qr ->
                scope.launch {
                    val activeIdentity = identity
                    val serviceResult = if (activeIdentity == null) {
                        serviceDeny("DEVICE_NOT_AUTHORIZED", "Dispositivo no pareado")
                    } else {
                        evaluateAndPersistService(activeIdentity, store, snapshot, qr)
                    }
                    result = serviceResult
                    feedback(context, serviceResult.decision)
                    syncOperationQueue(activeIdentity, store)
                    onSnapshot(snapshot.copy(queuePending = store.countPending()))
                }
            }
            result?.let { ServiceResultOverlay(it) }
        }
        if (BuildConfig.DEV_TOOLS_ENABLED) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            BitoraSecondaryButton("TEST CONSUME", Modifier.weight(1f)) {
                scope.launch {
                    val activeIdentity = identity ?: return@launch
                    result = evaluateAndPersistService(activeIdentity, store, snapshot, "BITORA:A5:VALID")
                    result?.let { feedback(context, it.decision) }
                    syncOperationQueue(activeIdentity, store)
                    onSnapshot(snapshot.copy(queuePending = store.countPending()))
                }
            }
            BitoraSecondaryButton("TEST DENY", Modifier.weight(1f)) {
                scope.launch {
                    val activeIdentity = identity ?: return@launch
                    result = evaluateAndPersistService(activeIdentity, store, snapshot, "BITORA:A5:DENY")
                    result?.let { feedback(context, it.decision) }
                    syncOperationQueue(activeIdentity, store)
                    onSnapshot(snapshot.copy(queuePending = store.countPending()))
                }
            }
        }
    }
}

@Composable
private fun ServiceResultOverlay(result: ServiceResult) {
    val color = if (result.decision == AccessDecision.ALLOW) BitoraColors.Success else BitoraColors.Error
    Column(
        Modifier.fillMaxWidth().heightIn(min = 260.dp).background(color).padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(result.title, color = Color.White, style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text(result.reasonCode, color = Color.White, style = MaterialTheme.typography.titleMedium)
        Text(result.detail, color = Color.White.copy(alpha = 0.9f))
    }
}

private suspend fun evaluateAndPersistService(
    identity: PairedDeviceIdentity,
    store: A2LocalStore,
    snapshot: BitoraDeviceSnapshot,
    qr: String,
): ServiceResult {
    val dataset = store.loadActiveDataset()
    val tokenHash = sha256(qr)
    val consumed = store.operationState("service_coffee", tokenHash) == "CONSUMED"
    val result = evaluateService(identity, dataset?.payloadJson, dataset?.organizationId, dataset?.eventId, dataset?.expiresAtEpochSeconds, qr, consumed)
    if (result.decision == AccessDecision.ALLOW) store.setOperationState("service_coffee", tokenHash, "CONSUMED")
    val operationId = UUID.randomUUID().toString()
    val payload = JSONObject()
        .put("event_id", identity.eventId)
        .put("device_id", identity.deviceId)
        .put("credential_ref", tokenHash)
        .put("entitlement_type", "COFFEE")
        .put("service_point", "coffee-main")
        .put("quantity", 1)
        .put("decision", result.decision.name)
        .put("reason_code", result.reasonCode)
        .put("device_timestamp", Instant.now().toString())
        .put("dataset_revision", snapshot.dataset.revision ?: store.activeRevision())
    store.enqueue(LocalQueueItem(
        operationId = operationId,
        idempotencyKey = "${identity.eventId}:CONSUME:COFFEE:$tokenHash",
        correlationId = UUID.randomUUID().toString(),
        operationType = "ENTITLEMENT_CONSUMPTION",
        payloadJson = payload.toString(),
        occurredAt = Instant.now().toString(),
        queuedAt = Instant.now().toString(),
        sequence = System.currentTimeMillis(),
    ))
    return result
}

internal fun evaluateService(
    identity: PairedDeviceIdentity,
    payloadJson: String?,
    datasetOrganizationId: Long?,
    datasetEventId: Long?,
    expiresAtEpochSeconds: Long?,
    qr: String,
    alreadyConsumed: Boolean,
    nowEpochSeconds: Long = Instant.now().epochSecond,
): ServiceResult {
    if (!qr.startsWith("BITORA:")) return serviceDeny("INVALID_QR", "QR no BITORA")
    if (payloadJson == null) return serviceDeny("DATASET_UNAVAILABLE", "Dataset no disponible")
    if (datasetOrganizationId != identity.organizationId || datasetEventId != identity.eventId) return serviceDeny("WRONG_EVENT", "Evento incorrecto")
    if ((expiresAtEpochSeconds ?: 0) <= nowEpochSeconds) return serviceDeny("DATASET_EXPIRED", "Dataset vencido")
    val capabilities = identity.capabilities.map { it.trim().uppercase() }.toSet()
    if (!capabilities.containsAll(setOf(BitoraCapability.CONSUME_ENTITLEMENT.name, BitoraCapability.SCAN_QR.name))) {
        return serviceDeny("DEVICE_NOT_AUTHORIZED", "Capabilities insuficientes")
    }
    if (identity.profile.trim().uppercase() != "SERVICE") return serviceDeny("DEVICE_NOT_AUTHORIZED", "Perfil no autorizado")
    val scope = identity.scope.trim().uppercase().split(':')
    if (scope.size != 3 || scope[0] != "EVENT" || scope[1].toLongOrNull() != identity.eventId || scope[2] != "SERVICE") {
        return serviceDeny("DEVICE_NOT_AUTHORIZED", "Scope no autorizado")
    }
    val payload = JSONObject(payloadJson)
    if (payload.optJSONObject("device")?.optString("profile").orEmpty().uppercase() != "SERVICE") {
        return serviceDeny("DEVICE_NOT_AUTHORIZED", "Dataset de otro perfil")
    }
    val items = payload.optJSONArray("service_entitlements") ?: JSONArray()
    val entitlement = (0 until items.length()).map { items.getJSONObject(it) }.firstOrNull { it.optString("token") == qr }
        ?: return serviceDeny("NO_ENTITLEMENT", "Beneficio no encontrado")
    if (entitlement.optLong("event_id") != identity.eventId) return serviceDeny("WRONG_EVENT", "Beneficio de otro evento")
    if (entitlement.optString("status") != "ACTIVE") return serviceDeny("REVOKED", "Beneficio inactivo")
    if (entitlement.optString("service_point") != "coffee-main") return serviceDeny("WRONG_SERVICE_POINT", "Punto de servicio incorrecto")
    if (entitlement.optInt("available", 0) < 1 || alreadyConsumed) return serviceDeny("ALREADY_CONSUMED", "Beneficio ya consumido")
    return ServiceResult(AccessDecision.ALLOW, "CONSUMED", "CONSUMO CONFIRMADO", entitlement.optString("display_name", "COFFEE"))
}

private fun serviceDeny(reason: String, detail: String) =
    ServiceResult(AccessDecision.DENY, reason, "CONSUMO DENEGADO", detail)
