package com.bitora.android.foundation.sync

import android.content.Context
import com.bitora.android.foundation.edge.DatasetVerifier
import com.bitora.android.foundation.edge.EdgeClient
import com.bitora.android.foundation.edge.EventDatasetEnvelope
import com.bitora.android.foundation.edge.HeartbeatTelemetry
import com.bitora.android.foundation.network.PairedDeviceIdentity
import com.bitora.android.foundation.persistence.A2LocalStore
import java.time.Instant
import org.json.JSONArray
import org.json.JSONObject

data class EdgeSyncResult(
    val success: Boolean,
    val revision: String? = null,
    val acknowledged: Int = 0,
    val pending: Int = 0,
    val reason: String? = null,
)

class EdgeSyncEngine(context: Context) {
    private val store = A2LocalStore(context.applicationContext)

    suspend fun sync(
        identity: PairedDeviceIdentity,
        flushOperations: Boolean,
        deviceKind: String = "",
        softwareVersion: String = "",
        environment: String = "",
    ): EdgeSyncResult = runCatching {
        val startedAt = System.nanoTime()
        val edge = EdgeClient(identity)
        val envelope = parseEnvelope(JSONObject(edge.dataset()))
        val verified = DatasetVerifier().verify(envelope, identity.organizationId, identity.eventId, store.activeRevision())
        if (!verified.ok) {
            return EdgeSyncResult(false, store.activeRevision(), pending = store.countPending(), reason = verified.reason)
        }

        store.saveActiveDataset(envelope)
        store.markSync(Instant.now().toString())
        val heartbeat = HeartbeatTelemetry(
            deviceKind = deviceKind,
            softwareVersion = softwareVersion,
            environment = environment,
            queuePending = store.countPending(),
            syncDurationMs = (System.nanoTime() - startedAt) / 1_000_000,
        )
        if (!edge.heartbeat(envelope.revision, heartbeat)) {
            return EdgeSyncResult(false, envelope.revision, pending = store.countPending(), reason = "heartbeat_failed")
        }
        store.markHeartbeat(Instant.now().toString())
        val acknowledged = if (flushOperations) flushOperations(identity, store) else 0
        EdgeSyncResult(true, envelope.revision, acknowledged, store.countPending())
    }.getOrElse {
        EdgeSyncResult(false, store.activeRevision(), pending = store.countPending(), reason = it.javaClass.simpleName)
    }

    companion object {
        suspend fun flushOperations(identity: PairedDeviceIdentity, store: A2LocalStore): Int {
            val pending = store.pending(50)
            if (pending.isEmpty()) return 0
            val operations = JSONArray()
            pending.forEach { item ->
                operations.put(
                    JSONObject()
                        .put("operationId", item.operationId)
                        .put("idempotencyKey", item.idempotencyKey)
                        .put("correlationId", item.correlationId)
                        .put("operationType", item.operationType)
                        .put("payload", JSONObject(item.payloadJson))
                        .put("sequence", item.sequence)
                )
            }
            val results = JSONObject(EdgeClient(identity).syncBatch(operations.toString())).optJSONArray("results") ?: JSONArray()
            var acknowledged = 0
            for (index in 0 until results.length()) {
                val result = results.getJSONObject(index)
                if (result.optString("status") in setOf("ACKNOWLEDGED", "DUPLICATE")) {
                    store.markAcknowledged(result.optString("operationId"))
                    acknowledged += 1
                }
            }
            return acknowledged
        }

        private fun parseEnvelope(obj: JSONObject) = EventDatasetEnvelope(
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
    }
}
