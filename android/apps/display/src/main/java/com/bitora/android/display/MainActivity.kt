package com.bitora.android.display

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import com.bitora.android.foundation.edge.DatasetVerifier
import com.bitora.android.foundation.edge.EdgeClient
import com.bitora.android.foundation.edge.EventDatasetEnvelope
import com.bitora.android.foundation.edge.HeartbeatTelemetry
import com.bitora.android.foundation.model.BitoraDatasetStatus
import com.bitora.android.foundation.model.BitoraDeviceSnapshot
import com.bitora.android.foundation.model.BitoraEdgeStatus
import com.bitora.android.foundation.model.DatasetState
import com.bitora.android.foundation.model.EdgeConnectionState
import com.bitora.android.foundation.model.PairingState
import com.bitora.android.foundation.network.HttpPairingClient
import com.bitora.android.foundation.network.EndpointPolicy
import com.bitora.android.foundation.network.PairedDeviceIdentity
import com.bitora.android.foundation.pairing.PairingSession
import com.bitora.android.foundation.pairing.SecureDeviceIdentityStore
import com.bitora.android.foundation.pairing.toSnapshot
import com.bitora.android.foundation.persistence.A2LocalStore
import com.bitora.android.foundation.theme.BitoraColors
import com.bitora.android.foundation.theme.BitoraTheme
import com.bitora.android.foundation.sync.BitoraBackgroundSync
import com.bitora.android.foundation.ui.BitoraCard
import com.bitora.android.foundation.ui.BitoraStatusBadge
import com.bitora.android.foundation.ui.StatusTone
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val store = SecureDeviceIdentityStore(this)
        val localStore = A2LocalStore(this)
        val configuredUrl = BuildConfig.BITORA_PAIRING_BASE_URL.trimEnd('/')
        val storedIdentity = runCatching { store.load() }.getOrNull()?.let { identity ->
            val migrated = if (BuildConfig.DEV_TOOLS_ENABLED && identity.edgeBaseUrl.contains(".trycloudflare.com") && configuredUrl.contains(".trycloudflare.com") && identity.edgeBaseUrl.trimEnd('/') != configuredUrl) identity.copy(edgeBaseUrl = configuredUrl).also(store::save) else identity
            migrated.takeIf { EndpointPolicy.isAllowed(it.edgeBaseUrl, BuildConfig.DEV_TOOLS_ENABLED) }
                ?: run { store.clear(); null }
        }
        val stored = storedIdentity?.toSnapshot()?.let { displayOfflineSnapshot(it, storedIdentity, localStore) }
        if (storedIdentity != null) BitoraBackgroundSync.schedule(this, "DISPLAY", BuildConfig.DEV_TOOLS_ENABLED)
        val client = configuredUrl.takeIf { EndpointPolicy.isAllowed(it, BuildConfig.DEV_TOOLS_ENABLED) }?.let { HttpPairingClient(it, BuildConfig.DEV_TOOLS_ENABLED) }
        val session = PairingSession(
            client = client,
            store = store,
            deviceKind = "DISPLAY",
            requestedProfile = "DISPLAY",
            softwareVersion = "android-a11-${BuildConfig.VERSION_NAME}",
        )
        val snapshot = stored ?: BitoraDeviceSnapshot(
            pairing = PairingState(
                code = session.code,
                expiresInLabel = "10 min",
                statusLabel = "PAIRING REQUIRED",
            )
        )
        setContent {
            BitoraTheme {
                DisplayShell(snapshot, session, storedIdentity, client != null)
            }
        }
    }
}

@Composable
fun DisplayShell(initialSnapshot: BitoraDeviceSnapshot = BitoraDeviceSnapshot(), session: PairingSession? = null, initialIdentity: PairedDeviceIdentity? = null, endpointConfigured: Boolean = true) {
    var snapshot by remember { mutableStateOf(initialSnapshot) }
    var identity by remember { mutableStateOf(initialIdentity) }
    var helper by remember { mutableStateOf(if (initialIdentity == null) "Tap the pairing card after admin approval to finish pairing." else "SYNCED") }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val localStore = remember { A2LocalStore(context) }
    var backgroundLabel by remember { mutableStateOf(localStore.backgroundSyncLabel()) }
    LaunchedEffect(Unit) {
        while (true) {
            backgroundLabel = localStore.backgroundSyncLabel()
            delay(1_000)
        }
    }
    val content = runCatching { JSONObject(localStore.loadActiveDataset()?.payloadJson ?: "{}").optJSONObject("display_content") }.getOrNull()
    Row(
        modifier = Modifier
            .fillMaxSize()
            .background(BitoraColors.Ink)
            .padding(24.dp),
        horizontalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.Center,
        ) {
            Text("BITORA", color = Color.White, style = MaterialTheme.typography.headlineLarge)
            Text(if (BuildConfig.DEV_TOOLS_ENABLED) "DISPLAY A10" else "DISPLAY", color = BitoraColors.ArenaLight, style = MaterialTheme.typography.headlineMedium)
            Spacer(Modifier.height(20.dp))
            BitoraStatusBadge(if (snapshot.identity.deviceId == null) "DISPLAY UNPAIRED" else "DISPLAY PAIRED", if (snapshot.identity.deviceId == null) StatusTone.Offline else StatusTone.Success)
            Spacer(Modifier.height(28.dp))
            Text(content?.optString("title", "DIGITAL SIGNAGE") ?: "DIGITAL SIGNAGE", color = Color.White, style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(12.dp))
            Text(content?.optString("message", "Waiting for verified content") ?: "Waiting for verified content", color = Color.White.copy(alpha = 0.82f), style = MaterialTheme.typography.headlineMedium)
            Text(content?.optString("screen", "-") ?: "-", color = BitoraColors.ArenaLight)
        }

        BitoraCard(Modifier.weight(1f)) {
            Text(if (snapshot.identity.deviceId == null) "Pairing required" else "Display ready", style = MaterialTheme.typography.headlineMedium)
            Spacer(Modifier.height(12.dp))
            Text(if (snapshot.identity.deviceId == null) "CODE" else "DEVICE", fontWeight = FontWeight.Bold, color = BitoraColors.Offline)
            Text(snapshot.pairing.code ?: snapshot.identity.deviceId ?: "PAIRED", style = MaterialTheme.typography.headlineLarge)
            Spacer(Modifier.height(8.dp))
            androidx.compose.material3.Button(onClick = {
                if (session != null && endpointConfigured && snapshot.identity.deviceId == null) {
                    scope.launch {
                        helper = "WAITING AUTHORIZATION"
                        val registered = session.register()
                        snapshot = snapshot.copy(pairing = registered.getOrNull() ?: PairingState(code = session.code, statusLabel = "PAIRING ERROR"))
                        val paired = session.exchangeIfApproved()
                        if (paired.isSuccess) {
                            val pairedIdentity = paired.getOrThrow()
                            identity = pairedIdentity
                            BitoraBackgroundSync.schedule(context, "DISPLAY", BuildConfig.DEV_TOOLS_ENABLED)
                            snapshot = syncDisplay(pairedIdentity, pairedIdentity.toSnapshot(), localStore)
                            helper = "PAIRED"
                        } else {
                            helper = "CHECK AUTHORIZATION"
                        }
                    }
                } else if (snapshot.identity.deviceId != null && identity != null) {
                    scope.launch { snapshot = syncDisplay(identity!!, snapshot, localStore); helper = "SYNCED" }
                }
            }) {
                Text(if (!endpointConfigured) "CONFIGURATION REQUIRED" else if (snapshot.identity.deviceId == null) "START PAIRING" else "SYNC CONTENT")
            }
            Spacer(Modifier.height(8.dp))
            Text(helper)
            if (BuildConfig.DEV_TOOLS_ENABLED) Text("Background: $backgroundLabel", color = BitoraColors.Offline)
            Spacer(Modifier.height(10.dp))
            Field("Device ID", snapshot.identity.deviceId ?: "-")
            Field("Event", snapshot.identity.eventName ?: "-")
            Field("Screen/Profile", snapshot.identity.scopeLabel ?: snapshot.identity.profile?.name ?: "DISPLAY")
            Field("Edge", snapshot.edge.status.name)
            Field("Dataset", snapshot.dataset.status.name)
            Field("Dataset revision", snapshot.dataset.revision ?: "-")
            Field("Last sync", snapshot.lastSyncLabel)
            Field("Queue pending", snapshot.queuePending.toString())
            Field("Aspect", "16:9 default / configurable")
        }
    }
}

private suspend fun syncDisplay(identity: PairedDeviceIdentity, base: BitoraDeviceSnapshot, store: A2LocalStore): BitoraDeviceSnapshot = runCatching {
    val startedAt = System.nanoTime()
    val edge = EdgeClient(identity)
    val obj = JSONObject(edge.dataset())
    val envelope = EventDatasetEnvelope(obj.getLong("organizationId"), obj.getLong("eventId"), obj.getString("revision"), obj.getString("schemaVersion"), obj.get("generatedAt").toString(), obj.getLong("expiresAtEpochSeconds"), obj.getString("payloadJson"), obj.getString("checksum"), obj.getString("signature"), obj.getString("signingKeyId"))
    val verified = DatasetVerifier(identity.credentialToken).verify(envelope, identity.organizationId, identity.eventId, store.activeRevision())
    if (verified.ok) { store.saveActiveDataset(envelope); store.markSync("Now") }
    val heartbeat = edge.heartbeat(
        envelope.revision,
        HeartbeatTelemetry(
            deviceKind = "DISPLAY",
            softwareVersion = BuildConfig.VERSION_NAME,
            environment = if (BuildConfig.DEV_TOOLS_ENABLED) "LAB" else "PRODUCTION",
            queuePending = store.countPending(),
            syncDurationMs = (System.nanoTime() - startedAt) / 1_000_000,
        ),
    )
    if (heartbeat) store.markHeartbeat("Now")
    base.copy(
        edge = EdgeConnectionState(identity.edgeBaseUrl, if (heartbeat) BitoraEdgeStatus.ONLINE else BitoraEdgeStatus.OFFLINE, if (heartbeat) "Now" else base.edge.lastSeenLabel),
        dataset = DatasetState(envelope.revision, verified.status, verified.reason, envelope.checksum, envelope.signature.take(12)),
        lastSyncLabel = store.lastSync(), lastHeartbeatLabel = store.lastHeartbeat(),
    )
}.getOrElse { displayOfflineSnapshot(base, identity, store) }

private fun displayOfflineSnapshot(base: BitoraDeviceSnapshot, identity: PairedDeviceIdentity, store: A2LocalStore): BitoraDeviceSnapshot {
    val cached = store.loadActiveDataset()
    val state = if (cached == null) base.dataset else {
        val verified = DatasetVerifier(identity.credentialToken).verify(cached, identity.organizationId, identity.eventId, null)
        DatasetState(cached.revision, if (verified.ok) BitoraDatasetStatus.CURRENT else verified.status, if (verified.ok) "Cached" else verified.reason, cached.checksum, cached.signature.take(12))
    }
    return base.copy(edge = base.edge.copy(status = BitoraEdgeStatus.OFFLINE), dataset = state, lastSyncLabel = store.lastSync(), lastHeartbeatLabel = store.lastHeartbeat())
}

@Composable
private fun Field(label: String, value: String) {
    Column(Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
        Text(label, color = BitoraColors.Offline)
        Text(value, style = MaterialTheme.typography.titleMedium)
    }
}
