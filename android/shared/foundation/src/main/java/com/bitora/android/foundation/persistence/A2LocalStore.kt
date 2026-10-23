package com.bitora.android.foundation.persistence

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.bitora.android.foundation.edge.EventDatasetEnvelope
import java.time.Instant
import org.json.JSONArray
import org.json.JSONObject

class A2LocalStore(context: Context) : BitoraLocalQueue {
    private val masterKey = MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
    private val prefs = EncryptedSharedPreferences.create(
        context,
        "bitora_a2_local_store",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    fun saveActiveDataset(envelope: EventDatasetEnvelope) {
        prefs.edit()
            .putLong("active_dataset_org", envelope.organizationId)
            .putLong("active_dataset_event", envelope.eventId)
            .putString("active_dataset_revision", envelope.revision)
            .putString("active_dataset_schema", envelope.schemaVersion)
            .putString("active_dataset_generated_at", envelope.generatedAt)
            .putLong("active_dataset_expires", envelope.expiresAtEpochSeconds)
            .putString("active_dataset_checksum", envelope.checksum)
            .putString("active_dataset_signature", envelope.signature)
            .putString("active_dataset_signing_key", envelope.signingKeyId)
            .putString("active_dataset_payload", envelope.payloadJson)
            .apply()
    }

    fun loadActiveDataset(): EventDatasetEnvelope? {
        val revision = prefs.getString("active_dataset_revision", null) ?: return null
        val payload = prefs.getString("active_dataset_payload", null) ?: return null
        val checksum = prefs.getString("active_dataset_checksum", null) ?: return null
        val signature = prefs.getString("active_dataset_signature", null) ?: return null
        return EventDatasetEnvelope(
            organizationId = prefs.getLong("active_dataset_org", -1),
            eventId = prefs.getLong("active_dataset_event", -1),
            revision = revision,
            schemaVersion = prefs.getString("active_dataset_schema", "v5.8") ?: "v5.8",
            generatedAt = prefs.getString("active_dataset_generated_at", "") ?: "",
            expiresAtEpochSeconds = prefs.getLong("active_dataset_expires", 0),
            payloadJson = payload,
            checksum = checksum,
            signature = signature,
            signingKeyId = prefs.getString("active_dataset_signing_key", "") ?: "",
        )
    }

    fun activeRevision(): String? = prefs.getString("active_dataset_revision", null)
    fun activeChecksum(): String? = prefs.getString("active_dataset_checksum", null)
    fun activeSignature(): String? = prefs.getString("active_dataset_signature", null)
    fun markHeartbeat(label: String) { prefs.edit().putString("last_heartbeat", label).apply() }
    fun markSync(label: String) { prefs.edit().putString("last_sync", label).apply() }
    fun lastHeartbeat(): String = prefs.getString("last_heartbeat", "Never") ?: "Never"
    fun lastSync(): String = prefs.getString("last_sync", "Never") ?: "Never"
    fun markBackgroundSync(status: String, reason: String? = null) {
        prefs.edit()
            .putString("background_sync_status", status)
            .putString("background_sync_reason", reason.orEmpty())
            .putString("background_sync_at", Instant.now().toString())
            .apply()
    }
    fun backgroundSyncLabel(): String {
        val status = prefs.getString("background_sync_status", "NEVER") ?: "NEVER"
        val reason = prefs.getString("background_sync_reason", "").orEmpty()
        return if (reason.isBlank()) status else "$status: $reason"
    }
    fun accessState(tokenHash: String): String = prefs.getString("access_state_$tokenHash", "OUTSIDE") ?: "OUTSIDE"
    fun setAccessState(tokenHash: String, state: String) { prefs.edit().putString("access_state_$tokenHash", state).apply() }
    fun lastAccessAt(tokenHash: String): Long = prefs.getLong("access_last_$tokenHash", 0L)
    fun setLastAccessAt(tokenHash: String, at: Long) { prefs.edit().putLong("access_last_$tokenHash", at).apply() }
    fun operationState(namespace: String, key: String, default: String = "NONE"): String =
        prefs.getString("operation_${namespace}_$key", default) ?: default
    fun setOperationState(namespace: String, key: String, state: String) {
        prefs.edit().putString("operation_${namespace}_$key", state).apply()
    }

    override suspend fun enqueue(item: LocalQueueItem) {
        val arr = queueArray()
        if ((0 until arr.length()).any { arr.getJSONObject(it).getString("idempotencyKey") == item.idempotencyKey }) return
        arr.put(JSONObject()
            .put("operationId", item.operationId)
            .put("idempotencyKey", item.idempotencyKey)
            .put("correlationId", item.correlationId)
            .put("operationType", item.operationType)
            .put("payloadJson", item.payloadJson)
            .put("occurredAt", item.occurredAt)
            .put("queuedAt", item.queuedAt)
            .put("retryCount", item.retryCount)
            .put("status", item.status.name)
            .put("sequence", item.sequence))
        saveQueue(arr)
    }

    override suspend fun pending(limit: Int): List<LocalQueueItem> {
        val arr = queueArray()
        val out = mutableListOf<LocalQueueItem>()
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            if (o.optString("status") == QueueItemStatus.PENDING.name && out.size < limit) {
                out.add(LocalQueueItem(
                    operationId = o.getString("operationId"),
                    idempotencyKey = o.getString("idempotencyKey"),
                    correlationId = o.getString("correlationId"),
                    operationType = o.getString("operationType"),
                    payloadJson = o.getString("payloadJson"),
                    occurredAt = o.getString("occurredAt"),
                    queuedAt = o.getString("queuedAt"),
                    retryCount = o.optInt("retryCount", 0),
                    sequence = o.optLong("sequence", 0),
                ))
            }
        }
        return out
    }

    override suspend fun markAcknowledged(operationId: String) {
        val arr = queueArray()
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            if (o.optString("operationId") == operationId) o.put("status", QueueItemStatus.ACKNOWLEDGED.name)
        }
        saveQueue(arr)
    }

    override suspend fun countPending(): Int {
        val arr = queueArray()
        return (0 until arr.length()).count { arr.getJSONObject(it).optString("status") == QueueItemStatus.PENDING.name }
    }

    private fun queueArray(): JSONArray = JSONArray(prefs.getString("queue", "[]") ?: "[]")
    private fun saveQueue(arr: JSONArray) { prefs.edit().putString("queue", arr.toString()).apply() }
}
