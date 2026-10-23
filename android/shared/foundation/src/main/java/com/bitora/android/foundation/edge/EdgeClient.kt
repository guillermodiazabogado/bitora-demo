package com.bitora.android.foundation.edge

import com.bitora.android.foundation.network.PairedDeviceIdentity
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

data class HeartbeatTelemetry(
    val deviceKind: String,
    val softwareVersion: String,
    val environment: String,
    val queuePending: Int,
    val syncDurationMs: Long,
) {
    fun toJson(): JSONObject = JSONObject()
        .put("deviceKind", deviceKind)
        .put("softwareVersion", softwareVersion)
        .put("environment", environment)
        .put("queuePending", queuePending)
        .put("syncDurationMs", syncDurationMs)
}

class EdgeClient(private val identity: PairedDeviceIdentity) {
    suspend fun heartbeat(datasetRevision: String?, telemetry: HeartbeatTelemetry? = null): Boolean = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("deviceId", identity.deviceId)
            .put("eventId", identity.eventId)
            .put("organizationId", identity.organizationId)
            .put("datasetRevision", datasetRevision.orEmpty())
        if (telemetry != null) body.put("telemetry", telemetry.toJson())
        val response = post("/api/edge/heartbeat", body.toString())
        response.contains(""""ok": true""") || response.contains(""""ok":true""")
    }

    suspend fun dataset(): String = withContext(Dispatchers.IO) {
        get("/api/edge/dataset?deviceId=${identity.deviceId}&eventId=${identity.eventId}&organizationId=${identity.organizationId}")
    }

    suspend fun syncBatch(itemsJson: String): String = withContext(Dispatchers.IO) {
        post("/api/edge/sync", """{"deviceId":"${identity.deviceId}","operations":$itemsJson}""")
    }

    private fun get(path: String): String = request("GET", path, null)
    private fun post(path: String, body: String): String = request("POST", path, body)

    private fun request(method: String, path: String, body: String?): String {
        val url = URL(identity.edgeBaseUrl.trimEnd('/') + path)
        val conn = (url.openConnection() as HttpURLConnection)
        conn.requestMethod = method
        conn.connectTimeout = 8000
        conn.readTimeout = 8000
        conn.setRequestProperty("Accept", "application/json")
        conn.setRequestProperty("X-Bitora-Device", identity.deviceId)
        conn.setRequestProperty("X-Bitora-Token", identity.credentialToken)
        if (body != null) {
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(body) }
        }
        val stream = if (conn.responseCode in 200..299) conn.inputStream else conn.errorStream
        return stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
    }
}
