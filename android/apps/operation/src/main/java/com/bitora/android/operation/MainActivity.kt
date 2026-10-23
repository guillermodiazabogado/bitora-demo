package com.bitora.android.operation

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.bitora.android.foundation.model.PairingState
import com.bitora.android.foundation.model.BitoraDatasetStatus
import com.bitora.android.foundation.model.BitoraEdgeStatus
import com.bitora.android.foundation.model.DatasetState
import com.bitora.android.foundation.model.EdgeConnectionState
import com.bitora.android.foundation.edge.DatasetVerifier
import com.bitora.android.foundation.edge.EdgeClient
import com.bitora.android.foundation.edge.EventDatasetEnvelope
import com.bitora.android.foundation.edge.HeartbeatTelemetry
import com.bitora.android.foundation.network.HttpPairingClient
import com.bitora.android.foundation.network.EndpointPolicy
import com.bitora.android.foundation.model.BitoraDeviceSnapshot
import com.bitora.android.foundation.model.BitoraOperationProfile
import com.bitora.android.foundation.network.PairedDeviceIdentity
import com.bitora.android.foundation.pairing.PairingSession
import com.bitora.android.foundation.pairing.SecureDeviceIdentityStore
import com.bitora.android.foundation.pairing.toSnapshot
import com.bitora.android.foundation.persistence.A2LocalStore
import com.bitora.android.foundation.theme.BitoraColors
import com.bitora.android.foundation.theme.BitoraTheme
import com.bitora.android.foundation.sync.BitoraBackgroundSync
import com.bitora.android.foundation.ui.BitoraButton
import com.bitora.android.foundation.ui.BitoraCard
import com.bitora.android.foundation.ui.BitoraDeviceStatus
import com.bitora.android.foundation.ui.BitoraSecondaryButton
import com.bitora.android.foundation.ui.BitoraStatusBadge
import com.bitora.android.foundation.ui.BitoraTopBar
import com.bitora.android.foundation.ui.StatusTone
import kotlinx.coroutines.launch
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val store = SecureDeviceIdentityStore(this)
        val a2Store = A2LocalStore(this)
        val configuredLabUrl = BuildConfig.BITORA_PAIRING_BASE_URL.trimEnd('/')
        val storedIdentity = runCatching { store.load() }.getOrNull()?.let { identity ->
            val oldLabTunnel = identity.edgeBaseUrl.contains(".trycloudflare.com")
            val currentLabTunnel = configuredLabUrl.contains(".trycloudflare.com")
            val migrated = if (BuildConfig.DEV_TOOLS_ENABLED && oldLabTunnel && currentLabTunnel && identity.edgeBaseUrl.trimEnd('/') != configuredLabUrl) {
                identity.copy(edgeBaseUrl = configuredLabUrl).also(store::save)
            } else {
                identity
            }
            migrated.takeIf { EndpointPolicy.isAllowed(it.edgeBaseUrl, BuildConfig.DEV_TOOLS_ENABLED) }
                ?: run { store.clear(); null }
        }
        val stored = storedIdentity?.toSnapshot()?.let { hydrateOfflineSnapshot(it, storedIdentity, a2Store) }
        if (storedIdentity != null) BitoraBackgroundSync.schedule(this, "OPERATION", BuildConfig.DEV_TOOLS_ENABLED)
        val client = configuredLabUrl.takeIf { EndpointPolicy.isAllowed(it, BuildConfig.DEV_TOOLS_ENABLED) }?.let { HttpPairingClient(it, BuildConfig.DEV_TOOLS_ENABLED) }
        val session = PairingSession(
            client = client,
            store = store,
            deviceKind = "OPERATION",
            requestedProfile = "SELF_SERVICE",
            softwareVersion = "android-a11-${BuildConfig.VERSION_NAME}",
        )
        val snapshot = stored ?: BitoraDeviceSnapshot(
            pairing = com.bitora.android.foundation.model.PairingState(
                code = session.code,
                expiresInLabel = "10 min",
                statusLabel = "PAIRING REQUIRED",
            )
        )
        setContent {
            BitoraTheme {
                OperationShell(snapshot, session, storedIdentity, client != null)
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun OperationShell(
    initialSnapshot: BitoraDeviceSnapshot = BitoraDeviceSnapshot(),
    session: PairingSession? = null,
    initialIdentity: PairedDeviceIdentity? = null,
    endpointConfigured: Boolean = true,
) {
    var snapshot by remember { mutableStateOf(initialSnapshot) }
    var pairedIdentity by remember { mutableStateOf(initialIdentity) }
    var actionLabel by remember { mutableStateOf(if (!endpointConfigured) "CONFIGURATION REQUIRED" else if (snapshot.identity.deviceId == null) "PAIR DEVICE" else "PAIRED") }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    Column(Modifier.fillMaxSize()) {
        BitoraTopBar(
            title = if (BuildConfig.DEV_TOOLS_ENABLED) "ANDROID A10 / SELF SERVICE" else "BITORA SELF SERVICE",
            subtitle = "Self Check-in + Badge Request + Offline",
        ) {
            if (BuildConfig.DEV_TOOLS_ENABLED) BitoraStatusBadge("DEV MODE", StatusTone.Warning)
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("BITORA OPERATION", style = MaterialTheme.typography.headlineMedium)
            Text(
                if (snapshot.identity.deviceId == null) "Pair this device from BITORA Admin to receive event, profile, scope and capabilities." else "Device identity is paired and stored securely.",
                color = BitoraColors.Offline,
            )

            BitoraDeviceStatus(
                deviceStatus = snapshot.identity.status,
                edgeStatus = snapshot.edge.status,
                datasetStatus = snapshot.dataset.status,
                modifier = Modifier.fillMaxWidth(),
            )

            if (snapshot.identity.deviceId == null) {
                BitoraCard(Modifier.fillMaxWidth()) {
                    Text("Pairing", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(8.dp))
                    Text("Status: ${snapshot.pairing.statusLabel}")
                    Text("Code: ${snapshot.pairing.code ?: "-"}")
                    Spacer(Modifier.height(12.dp))
                    BitoraButton(actionLabel, Modifier.fillMaxWidth()) {
                        if (session != null && endpointConfigured) {
                            scope.launch {
                                actionLabel = "WAITING AUTHORIZATION"
                                val registered = session.register()
                                snapshot = snapshot.copy(pairing = registered.getOrNull() ?: PairingState(code = session.code, statusLabel = "PAIRING ERROR"))
                                val paired = session.exchangeIfApproved()
                                if (paired.isSuccess) {
                                    val identity = paired.getOrThrow()
                                    pairedIdentity = identity
                                    BitoraBackgroundSync.schedule(context, "OPERATION", BuildConfig.DEV_TOOLS_ENABLED)
                                    val base = identity.toSnapshot()
                                    snapshot = syncEdgeDataset(identity, base, context)
                                    actionLabel = "PAIRED"
                                } else {
                                    actionLabel = "CHECK AUTHORIZATION"
                                }
                            }
                        }
                    }
                }
            }

            if (snapshot.identity.deviceId != null) {
                when (pairedIdentity?.profile?.trim()?.uppercase()) {
                    "RECEPTION" -> ReceptionPanel(pairedIdentity, snapshot, onSnapshot = { snapshot = it })
                    "SERVICE" -> ServicePanel(pairedIdentity, snapshot) { snapshot = it }
                    "LEAD_RETRIEVAL" -> LeadRetrievalPanel(pairedIdentity, snapshot) { snapshot = it }
                    "LOGISTICS" -> LogisticsPanel(pairedIdentity, snapshot) { snapshot = it }
                    "SELF_SERVICE" -> ReceptionPanel(pairedIdentity, snapshot, { snapshot = it }, "SELF_SERVICE", "SELF SERVICE", "Self check-in + badge request", "BITORA:A8:VALID", "BITORA:A8:DENY", "SELF_SERVICE_CHECK_IN")
                    else -> AccessFastPanel(pairedIdentity, snapshot) { snapshot = it }
                }
            }

            if (BuildConfig.DEV_TOOLS_ENABLED && snapshot.identity.deviceId != null) BitoraCard(Modifier.fillMaxWidth()) {
                Text("DEV diagnostics", fontWeight = FontWeight.SemiBold)
                Text("Dataset revision: ${snapshot.dataset.revision ?: "-"}")
                Text("Last sync: ${snapshot.lastSyncLabel}")
                Text("Queue pending: ${snapshot.queuePending}")
                Text("Last heartbeat: ${snapshot.lastHeartbeatLabel}")
                Text("Background sync: ${A2LocalStore(context).backgroundSyncLabel()}")
                Spacer(Modifier.height(8.dp))
                BitoraSecondaryButton("SYNC EDGE / DATASET", Modifier.fillMaxWidth()) {
                    scope.launch {
                        actionLabel = "SYNCING"
                        val identity = pairedIdentity
                        if (identity == null) {
                            snapshot = snapshot.copy(edge = snapshot.edge.copy(status = BitoraEdgeStatus.NOT_CONFIGURED))
                            actionLabel = "PAIR DEVICE"
                        } else {
                            snapshot = syncEdgeDataset(identity, snapshot, context)
                            actionLabel = "PAIRED"
                        }
                    }
                }
            }

            if (snapshot.identity.deviceId != null) BitoraCard(Modifier.fillMaxWidth()) {
                Text("Pairing", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                Text("Status: ${snapshot.pairing.statusLabel}")
                Text("Code: ${snapshot.pairing.code ?: "-"}")
                Text("Event: ${snapshot.identity.eventName ?: "-"}")
                Text("Profile: ${snapshot.identity.profile?.name ?: snapshot.identity.scopeLabel ?: "-"}")
                Text("Device: ${snapshot.identity.deviceId ?: "-"}")
                Spacer(Modifier.height(12.dp))
                BitoraButton(actionLabel, Modifier.fillMaxWidth()) {
                    if (session != null && snapshot.identity.deviceId == null) {
                        scope.launch {
                            actionLabel = "WAITING AUTHORIZATION"
                            val registered = session.register()
                            snapshot = snapshot.copy(pairing = registered.getOrNull() ?: PairingState(code = session.code, statusLabel = "PAIRING ERROR"))
                            val paired = session.exchangeIfApproved()
                            if (paired.isSuccess) {
                                val identity = paired.getOrThrow()
                                pairedIdentity = identity
                                BitoraBackgroundSync.schedule(context, "OPERATION", BuildConfig.DEV_TOOLS_ENABLED)
                                val base = identity.toSnapshot()
                                snapshot = syncEdgeDataset(identity, base, context)
                                actionLabel = "PAIRED"
                            } else {
                                actionLabel = "CHECK AUTHORIZATION"
                            }
                        }
                    }
                }
            }

            if (BuildConfig.DEV_TOOLS_ENABLED) BitoraCard(Modifier.fillMaxWidth()) {
                Text("DEV profile selector", fontWeight = FontWeight.SemiBold)
                Text("This selector is isolated for development and must be disabled for production.")
                Spacer(Modifier.height(12.dp))
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    BitoraOperationProfile.entries.forEach { profile ->
                        BitoraSecondaryButton(profile.name)
                    }
                }
            }
        }
    }
}

private suspend fun syncEdgeDataset(
    identity: PairedDeviceIdentity,
    base: BitoraDeviceSnapshot,
    context: android.content.Context,
): BitoraDeviceSnapshot {
    val store = A2LocalStore(context)
    val startedAt = System.nanoTime()
    return runCatching {
        val edge = EdgeClient(identity)
        val raw = edge.dataset()
        val obj = JSONObject(raw)
        val envelope = EventDatasetEnvelope(
            organizationId = obj.getLong("organizationId"),
            eventId = obj.getLong("eventId"),
            revision = obj.getString("revision"),
            schemaVersion = obj.getString("schemaVersion"),
            generatedAt = obj.get("generatedAt").toString(),
            expiresAtEpochSeconds = obj.getLong("expiresAtEpochSeconds"),
            payloadJson = obj.getString("payloadJson"),
            checksum = obj.getString("checksum"),
            signature = obj.getString("signature"),
            signingKeyId = obj.getString("signingKeyId"),
        )
        val verified = DatasetVerifier().verify(envelope, identity.organizationId, identity.eventId, store.activeRevision())
        if (verified.ok) {
            store.saveActiveDataset(envelope)
            store.markSync("Now")
        }
        val heartbeat = edge.heartbeat(
            envelope.revision,
            HeartbeatTelemetry(
                deviceKind = "OPERATION",
                softwareVersion = BuildConfig.VERSION_NAME,
                environment = if (BuildConfig.DEV_TOOLS_ENABLED) "LAB" else "PRODUCTION",
                queuePending = store.countPending(),
                syncDurationMs = (System.nanoTime() - startedAt) / 1_000_000,
            ),
        )
        if (heartbeat) store.markHeartbeat("Now")
        if (heartbeat) syncOperationQueue(identity, store)
        base.copy(
            edge = EdgeConnectionState(
                edgeUrl = identity.edgeBaseUrl,
                status = if (heartbeat) BitoraEdgeStatus.ONLINE else BitoraEdgeStatus.OFFLINE,
                lastSeenLabel = if (heartbeat) "Now" else base.edge.lastSeenLabel,
            ),
            dataset = DatasetState(
                revision = envelope.revision,
                status = verified.status,
                freshnessLabel = verified.reason,
                checksum = envelope.checksum,
                signature = envelope.signature.take(12),
            ),
            queuePending = store.countPending(),
            lastSyncLabel = store.lastSync(),
            lastHeartbeatLabel = store.lastHeartbeat(),
        )
    }.getOrElse {
        offlineSnapshot(base, identity, store)
    }
}

private fun hydrateOfflineSnapshot(
    base: BitoraDeviceSnapshot,
    identity: PairedDeviceIdentity,
    store: A2LocalStore,
): BitoraDeviceSnapshot = offlineSnapshot(base, identity, store)

private fun offlineSnapshot(
    base: BitoraDeviceSnapshot,
    identity: PairedDeviceIdentity,
    store: A2LocalStore,
): BitoraDeviceSnapshot {
    val cached = store.loadActiveDataset()
    val datasetState = if (cached != null) {
        val verified = DatasetVerifier().verify(cached, identity.organizationId, identity.eventId, null)
        DatasetState(
            revision = cached.revision,
            status = if (verified.ok) BitoraDatasetStatus.CURRENT else verified.status,
            freshnessLabel = if (verified.ok) "Cached" else verified.reason,
            checksum = cached.checksum,
            signature = cached.signature.take(12),
        )
    } else {
        base.dataset.copy(status = if (base.dataset.revision != null) base.dataset.status else BitoraDatasetStatus.NOT_AVAILABLE)
    }
    return base.copy(
        edge = base.edge.copy(status = BitoraEdgeStatus.OFFLINE),
        dataset = datasetState,
        queuePending = base.queuePending,
        lastSyncLabel = store.lastSync(),
        lastHeartbeatLabel = store.lastHeartbeat(),
    )
}
