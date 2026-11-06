package com.bitora.android.foundation.model

enum class BitoraDeviceStatus {
    UNPAIRED,
    PAIRING_REQUIRED,
    PAIRING_PENDING,
    PAIRED,
    PROVISIONED,
    ACTIVE,
    SUSPENDED,
    REVOKED,
}

enum class BitoraEdgeStatus {
    NOT_CONFIGURED,
    CONNECTING,
    ONLINE,
    STALE,
    DEGRADED,
    OFFLINE,
    ERROR,
}

enum class BitoraDatasetStatus {
    NOT_AVAILABLE,
    CURRENT,
    STALE,
    EXPIRED,
    INVALID,
}

enum class BitoraCapability {
    VALIDATE_ACCESS,
    CHECK_IN,
    CHECK_OUT,
    SCAN_QR,
    PRINT_BADGE,
    REGISTER,
    VIEW_PARTICIPANT,
    CONSUME_ENTITLEMENT,
    SYNC_DATASET,
    DISPLAY_CONTENT,
}

enum class BitoraOperationProfile {
    ACCESS_FAST,
    RECEPTION,
    SERVICE,
    LEAD_RETRIEVAL,
    LOGISTICS,
    SELF_SERVICE,
}

data class DeviceIdentityState(
    val deviceId: String? = null,
    val organizationId: Long? = null,
    val eventId: Long? = null,
    val status: BitoraDeviceStatus = BitoraDeviceStatus.UNPAIRED,
    val capabilities: Set<BitoraCapability> = emptySet(),
    val profile: BitoraOperationProfile? = null,
    val eventName: String? = null,
    val scopeLabel: String? = null,
    val credentialTokenPreview: String? = null,
)

data class EdgeConnectionState(
    val edgeUrl: String? = null,
    val status: BitoraEdgeStatus = BitoraEdgeStatus.NOT_CONFIGURED,
    val lastSeenLabel: String = "Never",
)

data class DatasetState(
    val revision: String? = null,
    val status: BitoraDatasetStatus = BitoraDatasetStatus.NOT_AVAILABLE,
    val freshnessLabel: String = "Unavailable",
    val checksum: String? = null,
    val signature: String? = null,
)

data class PairingState(
    val code: String? = null,
    val expiresInLabel: String? = null,
    val statusLabel: String = "PAIRING REQUIRED",
    val isPlaceholder: Boolean = false,
    val canReplay: Boolean = false,
)

data class BitoraDeviceSnapshot(
    val identity: DeviceIdentityState = DeviceIdentityState(),
    val edge: EdgeConnectionState = EdgeConnectionState(),
    val dataset: DatasetState = DatasetState(),
    val pairing: PairingState = PairingState(code = null),
    val queuePending: Int = 0,
    val lastSyncLabel: String = "Never",
    val lastHeartbeatLabel: String = "Never",
)
