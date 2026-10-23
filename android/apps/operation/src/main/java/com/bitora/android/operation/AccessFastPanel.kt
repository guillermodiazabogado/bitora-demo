package com.bitora.android.operation

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.OptIn
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
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
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.bitora.android.foundation.model.BitoraCapability
import com.bitora.android.foundation.model.BitoraDeviceSnapshot
import com.bitora.android.foundation.network.PairedDeviceIdentity
import com.bitora.android.foundation.persistence.A2LocalStore
import com.bitora.android.foundation.persistence.LocalQueueItem
import com.bitora.android.foundation.theme.BitoraColors
import com.bitora.android.foundation.sync.EdgeSyncEngine
import com.bitora.android.foundation.ui.BitoraButton
import com.bitora.android.foundation.ui.BitoraCard
import com.bitora.android.foundation.ui.BitoraSecondaryButton
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.security.MessageDigest
import java.time.Instant
import java.text.Normalizer
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

enum class AccessDirection { ENTRY, EXIT }
enum class AccessDecision { ALLOW, DENY }

data class AccessResult(
    val decision: AccessDecision,
    val reasonCode: String,
    val title: String,
    val detail: String,
    val direction: AccessDirection,
)

@Composable
fun AccessFastPanel(
    identity: PairedDeviceIdentity?,
    snapshot: BitoraDeviceSnapshot,
    onSnapshot: (BitoraDeviceSnapshot) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { A2LocalStore(context) }
    val configuredDirection = remember {
        runCatching {
            AccessDirection.valueOf(JSONObject(store.loadActiveDataset()?.payloadJson ?: "{}").optJSONObject("device")?.optString("direction", "ENTRY") ?: "ENTRY")
        }.getOrDefault(AccessDirection.ENTRY)
    }
    val directionState = remember { mutableStateOf(configuredDirection) }
    var result by remember { mutableStateOf<AccessResult?>(null) }
    var lastTokenHash by remember { mutableStateOf<String?>(null) }
    var lastScanAt by remember { mutableLongStateOf(0L) }

    LaunchedEffect(result) {
        if (result != null) {
            delay(1600)
            result = null
        }
    }

    BitoraCard(Modifier.fillMaxWidth()) {
        Text("ACCESS_FAST", fontWeight = FontWeight.SemiBold)
        Text("Door main / Zone general / ${directionState.value.name}", color = BitoraColors.Offline)
        if (BuildConfig.DEV_TOOLS_ENABLED) {
            Text("DEV direction", color = BitoraColors.Offline, style = MaterialTheme.typography.labelMedium)
            Spacer(Modifier.height(8.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                BitoraSecondaryButton("ENTRY", Modifier.weight(1f)) { directionState.value = AccessDirection.ENTRY }
                BitoraSecondaryButton("EXIT", Modifier.weight(1f)) { directionState.value = AccessDirection.EXIT }
            }
        }
        Spacer(Modifier.height(12.dp))
        Box {
            CameraQrScanner(
                enabled = identity != null && result == null,
                onQr = { qr ->
                    val now = System.currentTimeMillis()
                    val tokenHash = sha256(qr)
                    if (tokenHash == lastTokenHash && now - lastScanAt < 1600) return@CameraQrScanner
                    lastTokenHash = tokenHash
                    lastScanAt = now
                    scope.launch {
                        val activeIdentity = identity
                        val scanDirection = directionState.value
                        val accessResult = if (activeIdentity == null) {
                            AccessResult(AccessDecision.DENY, "DEVICE_NOT_AUTHORIZED", "ACCESO DENEGADO", "Dispositivo no pareado", scanDirection)
                        } else {
                            evaluateAndPersistAccess(context, activeIdentity, store, snapshot, qr, scanDirection)
                        }
                        result = accessResult
                        feedback(context, accessResult.decision)
                        syncOperationQueue(activeIdentity, store)
                        onSnapshot(snapshot.copy(queuePending = store.countPending()))
                    }
                },
            )
            result?.let { AccessResultOverlay(it) }
        }
        if (BuildConfig.DEV_TOOLS_ENABLED) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            BitoraSecondaryButton("TEST VALID", Modifier.weight(1f)) {
                scope.launch {
                    val activeIdentity = identity ?: return@launch
                    result = evaluateAndPersistAccess(context, activeIdentity, store, snapshot, "BITORA:A3:VALID", directionState.value)
                    result?.let { feedback(context, it.decision) }
                    syncOperationQueue(activeIdentity, store)
                    onSnapshot(snapshot.copy(queuePending = store.countPending()))
                }
            }
            BitoraSecondaryButton("TEST DENY", Modifier.weight(1f)) {
                scope.launch {
                    val activeIdentity = identity ?: return@launch
                    result = evaluateAndPersistAccess(context, activeIdentity, store, snapshot, "BITORA:A3:DENY", directionState.value)
                    result?.let { feedback(context, it.decision) }
                    syncOperationQueue(activeIdentity, store)
                    onSnapshot(snapshot.copy(queuePending = store.countPending()))
                }
            }
        }
    }
}

@Composable
internal fun CameraQrScanner(enabled: Boolean, onQr: (String) -> Unit) {
    val context = LocalContext.current
    val currentEnabled = rememberUpdatedState(enabled)
    val currentOnQr = rememberUpdatedState(onQr)
    var granted by remember { mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted = it }
    if (!granted) {
        BitoraButton("ENABLE CAMERA", Modifier.fillMaxWidth()) { launcher.launch(Manifest.permission.CAMERA) }
        return
    }
    val lifecycleOwner = LocalLifecycleOwner.current
    AndroidView(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 260.dp, max = 360.dp)
            .background(Color.Black),
        factory = { ctx ->
            val previewView = PreviewView(ctx)
            val providerFuture = ProcessCameraProvider.getInstance(ctx)
            providerFuture.addListener({
                val provider = providerFuture.get()
                val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
                val scanner = BarcodeScanning.getClient()
                val processing = AtomicBoolean(false)
                val lastQr = AtomicReference<String?>(null)
                val emptyFrames = AtomicInteger(0)
                val analysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                analysis.setAnalyzer(Executors.newSingleThreadExecutor()) { proxy ->
                    scanFrame(proxy, scanner, currentEnabled.value, processing, lastQr, emptyFrames, currentOnQr.value)
                }
                provider.unbindAll()
                provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
            }, ContextCompat.getMainExecutor(ctx))
            previewView
        },
    )
}

@OptIn(ExperimentalGetImage::class)
private fun scanFrame(
    proxy: androidx.camera.core.ImageProxy,
    scanner: com.google.mlkit.vision.barcode.BarcodeScanner,
    enabled: Boolean,
    processing: AtomicBoolean,
    lastQr: AtomicReference<String?>,
    emptyFrames: AtomicInteger,
    onQr: (String) -> Unit,
) {
    val image = proxy.image
    if (!enabled || image == null || !processing.compareAndSet(false, true)) {
        proxy.close()
        return
    }
    val input = InputImage.fromMediaImage(image, proxy.imageInfo.rotationDegrees)
    scanner.process(input)
        .addOnSuccessListener { codes ->
            val value = codes.firstOrNull { it.format == Barcode.FORMAT_QR_CODE }?.rawValue
            if (value.isNullOrBlank()) {
                if (emptyFrames.incrementAndGet() >= 5) lastQr.set(null)
            } else {
                emptyFrames.set(0)
                if (lastQr.getAndSet(value) != value) onQr(value)
            }
        }
        .addOnCompleteListener {
            processing.set(false)
            proxy.close()
        }
}

@Composable
private fun AccessResultOverlay(result: AccessResult) {
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
        Text("${result.direction.name} / ${result.reasonCode}", color = Color.White, style = MaterialTheme.typography.titleMedium)
        Text(result.detail, color = Color.White.copy(alpha = 0.9f))
    }
}

private suspend fun evaluateAndPersistAccess(
    context: Context,
    identity: PairedDeviceIdentity,
    store: A2LocalStore,
    snapshot: BitoraDeviceSnapshot,
    qr: String,
    direction: AccessDirection,
): AccessResult {
    val decision = evaluateAccess(identity, store, snapshot, qr, direction)
    val tokenHash = sha256(qr)
    val nextState = when {
        decision.decision == AccessDecision.ALLOW && direction == AccessDirection.ENTRY -> "INSIDE"
        decision.decision == AccessDecision.ALLOW && direction == AccessDirection.EXIT -> "OUTSIDE"
        else -> store.accessState(tokenHash)
    }
    if (decision.decision == AccessDecision.ALLOW) {
        store.setAccessState(tokenHash, nextState)
        store.setLastAccessAt(tokenHash, System.currentTimeMillis())
    }
    val payload = JSONObject()
        .put("event_id", identity.eventId)
        .put("device_id", identity.deviceId)
        .put("token_hash", tokenHash)
        .put("door", "main")
        .put("zone", "general")
        .put("direction", direction.name)
        .put("decision", decision.decision.name)
        .put("reason_code", decision.reasonCode)
        .put("local_access_state", nextState)
        .put("device_timestamp", Instant.now().toString())
        .put("dataset_revision", snapshot.dataset.revision ?: store.activeRevision())
        .toString()
    val operationId = UUID.randomUUID().toString()
    store.enqueue(
        LocalQueueItem(
            operationId = operationId,
            idempotencyKey = "$tokenHash:${direction.name}:${snapshot.dataset.revision}:${System.currentTimeMillis() / 1500}",
            correlationId = UUID.randomUUID().toString(),
            operationType = "ACCESS_ATTEMPT",
            payloadJson = payload,
            occurredAt = Instant.now().toString(),
            queuedAt = Instant.now().toString(),
            sequence = System.currentTimeMillis(),
        )
    )
    return decision
}

private fun evaluateAccess(
    identity: PairedDeviceIdentity,
    store: A2LocalStore,
    snapshot: BitoraDeviceSnapshot,
    qr: String,
    direction: AccessDirection,
): AccessResult {
    if (!qr.startsWith("BITORA:")) return deny("INVALID_QR", "QR no BITORA", direction)
    val dataset = store.loadActiveDataset() ?: return deny("DATASET_UNAVAILABLE", "Dataset no disponible", direction)
    if (dataset.eventId != identity.eventId || dataset.organizationId != identity.organizationId) return deny("WRONG_EVENT", "Evento incorrecto", direction)
    val payload = JSONObject(dataset.payloadJson)
    val deviceConfig = payload.optJSONObject("device")
    val authorization = authorizeAccessDevice(
        identity = identity,
        datasetOrganizationId = dataset.organizationId,
        datasetEventId = dataset.eventId,
        datasetProfile = deviceConfig?.optString("profile").orEmpty(),
        door = deviceConfig?.optString("door").orEmpty(),
        zone = deviceConfig?.optString("zone").orEmpty(),
        configuredDirection = if (BuildConfig.DEBUG) direction.name else deviceConfig?.optString("direction").orEmpty(),
        requestedDirection = direction,
    )
    if (!authorization.allowed) return deny("DEVICE_NOT_AUTHORIZED", authorization.detail, direction)
    val credentials = payload.optJSONArray("credentials") ?: JSONArray()
    val credential = (0 until credentials.length()).map { credentials.getJSONObject(it) }.firstOrNull { it.optString("token") == qr }
        ?: return deny("UNKNOWN_CREDENTIAL", "Credencial desconocida", direction)
    if (credential.optLong("event_id") != identity.eventId) return deny("WRONG_EVENT", "Credencial de otro evento", direction)
    if (credential.optString("status") == "REVOKED") return deny("REVOKED", "Credencial revocada", direction)
    if (credential.optString("status") != "ACTIVE") return deny("UNKNOWN_CREDENTIAL", "Credencial inactiva", direction)
    val entitlements = credential.optJSONArray("entitlements") ?: JSONArray()
    if ((0 until entitlements.length()).none { entitlements.optString(it) == "ACCESS_FAST" }) return deny("NO_ENTITLEMENT", "Sin permiso de acceso", direction)
    val doors = credential.optJSONArray("doors") ?: JSONArray()
    if ((0 until doors.length()).none { doors.optString(it) == "main" }) return deny("WRONG_DOOR", "Puerta no autorizada", direction)
    val zones = credential.optJSONArray("zones") ?: JSONArray()
    if ((0 until zones.length()).none { zones.optString(it) == "general" }) return deny("WRONG_ZONE", "Zona no autorizada", direction)
    val tokenHash = sha256(qr)
    val cooldownSeconds = payload.optJSONObject("configuration")?.optLong("cooldown_seconds", 2L) ?: 2L
    if (System.currentTimeMillis() - store.lastAccessAt(tokenHash) < cooldownSeconds * 1000L) return deny("COOLDOWN", "Lectura repetida", direction)
    val state = store.accessState(tokenHash)
    if (direction == AccessDirection.ENTRY && state == "INSIDE") return deny("ALREADY_INSIDE", "Ya se encuentra dentro", direction)
    if (direction == AccessDirection.EXIT && state == "OUTSIDE") return deny("ALREADY_OUTSIDE", "Ya se encuentra fuera", direction)
    val label = credential.optString("name", "Credencial valida")
    return AccessResult(AccessDecision.ALLOW, "VALID", "ACCESO PERMITIDO", label, direction)
}

internal data class DeviceAuthorizationResult(
    val allowed: Boolean,
    val normalizedProfile: String?,
    val detail: String,
)

internal fun authorizeAccessDevice(
    identity: PairedDeviceIdentity,
    datasetOrganizationId: Long,
    datasetEventId: Long,
    datasetProfile: String,
    door: String,
    zone: String,
    configuredDirection: String,
    requestedDirection: AccessDirection,
): DeviceAuthorizationResult {
    val capabilities = identity.capabilities.map { it.trim().uppercase() }.toSet()
    if (!capabilities.containsAll(setOf(BitoraCapability.VALIDATE_ACCESS.name, BitoraCapability.SCAN_QR.name))) {
        return DeviceAuthorizationResult(false, null, "Dispositivo sin permiso")
    }
    if (datasetOrganizationId != identity.organizationId || datasetEventId != identity.eventId) {
        return DeviceAuthorizationResult(false, null, "Scope de evento no autorizado")
    }
    val normalized = normalizedAccessProfile(identity)
    if (normalized != "ACCESS_FAST") return DeviceAuthorizationResult(false, normalized, "Perfil no autorizado")
    if (normalizeProfileValue(datasetProfile) != "ACCESS_FAST") return DeviceAuthorizationResult(false, normalized, "Perfil de dataset no autorizado")
    if (door.trim().lowercase() != "main" || zone.trim().lowercase() != "general") {
        return DeviceAuthorizationResult(false, normalized, "Puerta o zona no autorizada")
    }
    if (configuredDirection.trim().uppercase() != requestedDirection.name) {
        return DeviceAuthorizationResult(false, normalized, "Direccion no autorizada")
    }
    return DeviceAuthorizationResult(true, normalized, "Autorizado")
}

internal fun normalizedAccessProfile(identity: PairedDeviceIdentity): String? {
    val direct = normalizeProfileValue(identity.profile)
    if (direct != null) return direct

    val profileScope = identity.profile.trim().uppercase().split(':')
    if (profileScope.size == 3 && profileScope[0] == "EVENT" && profileScope[1].toLongOrNull() == identity.eventId && normalizeProfileValue(profileScope[2]) == "ACCESS_FAST") {
        return "ACCESS_FAST"
    }

    val assignedScope = identity.scope.trim().uppercase().split(':')
    if (assignedScope.size == 3 && assignedScope[0] == "EVENT" && assignedScope[1].toLongOrNull() == identity.eventId && normalizeProfileValue(assignedScope[2]) == "ACCESS_FAST") {
        return "ACCESS_FAST"
    }
    return null
}

private fun normalizeProfileValue(value: String): String? = when (
    Normalizer.normalize(value, Normalizer.Form.NFD)
        .replace(Regex("\\p{M}+"), "")
        .replace('\u00A0', ' ')
        .trim()
        .replace(Regex("\\s+"), " ")
        .uppercase()
) {
    "ACCESS_FAST", "ACCESO", "ACCESO RAPIDO" -> "ACCESS_FAST"
    else -> null
}

internal suspend fun syncOperationQueue(identity: PairedDeviceIdentity?, store: A2LocalStore) {
    if (identity == null) return
    runCatching { EdgeSyncEngine.flushOperations(identity, store) }
}

private fun deny(reason: String, detail: String, direction: AccessDirection): AccessResult =
    AccessResult(AccessDecision.DENY, reason, "ACCESO DENEGADO", detail, direction)

internal fun sha256(value: String): String {
    val bytes = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
    return bytes.joinToString("") { "%02x".format(it) }
}

internal fun feedback(context: Context, decision: AccessDecision) {
    runCatching {
        val tone = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 80)
        tone.startTone(if (decision == AccessDecision.ALLOW) ToneGenerator.TONE_PROP_ACK else ToneGenerator.TONE_PROP_NACK, 130)
    }
    runCatching {
        val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            (context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.vibrate(VibrationEffect.createOneShot(if (decision == AccessDecision.ALLOW) 80 else 180, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(if (decision == AccessDecision.ALLOW) 80 else 180)
        }
    }
}
