package com.bitora.android.foundation.network

import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URLEncoder
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class HttpPairingClient(
    private val baseUrl: String,
    private val allowLabEndpoints: Boolean = true,
) : BitoraPairingClient {
    init {
        require(EndpointPolicy.isAllowed(baseUrl, allowLabEndpoints)) { "pairing_endpoint_not_allowed" }
    }

    override suspend fun registerPairing(request: PairingRequest): Result<PairingStatus> = runCatching {
        val response = post(
            "/api/device-pairing/request",
            """{"pairingCode":"${esc(request.pairingCode)}","deviceKind":"${esc(request.deviceKind)}","requestedProfile":"${esc(request.requestedProfile)}","softwareVersion":"${esc(request.softwareVersion)}","nonce":"${esc(request.nonce)}"}""",
        )
        statusFrom(response)
    }

    override suspend fun checkPairing(pairingCode: String, nonce: String): Result<PairingStatus> = runCatching {
        val response = get("/api/device-pairing/status?pairingCode=${enc(pairingCode)}&nonce=${enc(nonce)}")
        statusFrom(response)
    }

    override suspend fun exchangePairing(pairingCode: String, nonce: String): Result<PairedDeviceIdentity> = runCatching {
        val response = post(
            "/api/device-pairing/exchange",
            """{"pairingCode":"${esc(pairingCode)}","nonce":"${esc(nonce)}"}""",
        )
        if (!bool(response, "ok")) error(field(response, "error") ?: "pairing_exchange_failed")
        val edgeBaseUrl = field(response, "edgeBaseUrl") ?: baseUrl
        require(EndpointPolicy.isAllowed(edgeBaseUrl, allowLabEndpoints)) { "edge_endpoint_not_allowed" }
        PairedDeviceIdentity(
            deviceId = field(response, "deviceId") ?: error("missing_device_id"),
            organizationId = number(response, "organizationId") ?: 0L,
            eventId = number(response, "eventId") ?: 0L,
            eventName = field(response, "eventName") ?: "",
            profile = field(response, "profile") ?: "",
            scope = field(response, "scope") ?: "",
            capabilities = array(response, "capabilities").toSet(),
            edgeBaseUrl = edgeBaseUrl,
            datasetRevision = field(response, "datasetRevision"),
            credentialToken = field(response, "credentialToken") ?: error("missing_credential"),
        )
    }

    private fun statusFrom(json: String): PairingStatus {
        val decision = runCatching { PairingDecision.valueOf(field(json, "decision") ?: field(json, "status") ?: "PENDING") }.getOrDefault(PairingDecision.PENDING)
        return PairingStatus(
            decision = decision,
            expiresAt = field(json, "expiresAt") ?: "",
            eventId = number(json, "eventId"),
            eventName = field(json, "eventName"),
            profile = field(json, "profile"),
            scope = field(json, "scope"),
        )
    }

    private suspend fun get(path: String): String = request("GET", path, null)
    private suspend fun post(path: String, body: String): String = request("POST", path, body)

    private suspend fun request(method: String, path: String, body: String?): String = withContext(Dispatchers.IO) {
        val url = URL(baseUrl.trimEnd('/') + path)
        val conn = (url.openConnection() as HttpURLConnection)
        conn.requestMethod = method
        conn.connectTimeout = 8000
        conn.readTimeout = 8000
        conn.setRequestProperty("Accept", "application/json")
        if (body != null) {
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(body) }
        }
        val stream = if (conn.responseCode in 200..299) conn.inputStream else conn.errorStream
        stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
    }

    private fun esc(value: String): String = value.replace("\\", "\\\\").replace("\"", "\\\"")
    private fun enc(value: String): String = URLEncoder.encode(value, "UTF-8")
    private fun bool(json: String, key: String): Boolean = Regex(""""$key"\s*:\s*true""").containsMatchIn(json)
    private fun field(json: String, key: String): String? = Regex(""""$key"\s*:\s*"([^"]*)"""").find(json)?.groupValues?.get(1)
    private fun number(json: String, key: String): Long? = Regex(""""$key"\s*:\s*([0-9]+)""").find(json)?.groupValues?.get(1)?.toLongOrNull()
    private fun array(json: String, key: String): List<String> {
        val raw = Regex(""""$key"\s*:\s*\[(.*?)\]""").find(json)?.groupValues?.get(1) ?: return emptyList()
        return Regex(""""([^"]+)"""").findAll(raw).map { it.groupValues[1] }.toList()
    }
}
