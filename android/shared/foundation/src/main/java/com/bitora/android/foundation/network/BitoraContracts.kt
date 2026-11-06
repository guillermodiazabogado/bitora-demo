package com.bitora.android.foundation.network

object BitoraContracts {
    const val DEVICE_CONTRACT_VERSION = "v5.8"
    const val DATASET_SCHEMA_VERSION = "v5.8"
    const val PAIRING_FLOW = "pairing_code_admin_authorization_device_identity"
    const val PAIRING_CODE_TTL_MINUTES = 10
    const val PAIRING_REQUEST_PATH = "/api/device-pairing/request"
    const val PAIRING_STATUS_PATH = "/api/device-pairing/status"
    const val PAIRING_EXCHANGE_PATH = "/api/device-pairing/exchange"
}

enum class PairingDecision {
    PENDING,
    APPROVED,
    REJECTED,
    EXPIRED,
    USED,
    REVOKED,
}

data class PairingRequest(
    val pairingCode: String,
    val deviceKind: String,
    val requestedProfile: String,
    val softwareVersion: String,
    val nonce: String,
)

data class PairingStatus(
    val decision: PairingDecision,
    val expiresAt: String,
    val eventId: Long? = null,
    val eventName: String? = null,
    val profile: String? = null,
    val scope: String? = null,
)

data class PairedDeviceIdentity(
    val deviceId: String,
    val organizationId: Long,
    val eventId: Long,
    val eventName: String,
    val profile: String,
    val scope: String,
    val capabilities: Set<String>,
    val edgeBaseUrl: String,
    val datasetRevision: String?,
    val credentialToken: String,
)

interface BitoraPairingClient {
    suspend fun registerPairing(request: PairingRequest): Result<PairingStatus>
    suspend fun checkPairing(pairingCode: String, nonce: String): Result<PairingStatus>
    suspend fun exchangePairing(pairingCode: String, nonce: String): Result<PairedDeviceIdentity>
}

data class OperationEnvelope(
    val operationId: String,
    val idempotencyKey: String,
    val organizationId: Long,
    val eventId: Long,
    val edgeId: String?,
    val deviceId: String,
    val capability: String,
    val deviceTimestamp: String,
    val sequence: Long,
    val datasetRevision: String?,
    val payloadVersion: String,
    val correlationId: String,
)

interface BitoraEdgeClient {
    suspend fun heartbeat(deviceId: String, datasetRevision: String?): Result<Unit>
    suspend fun fetchDatasetRevision(eventId: Long): Result<String>
}
