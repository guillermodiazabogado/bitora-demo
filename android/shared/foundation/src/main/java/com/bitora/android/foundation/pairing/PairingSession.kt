package com.bitora.android.foundation.pairing

import com.bitora.android.foundation.model.BitoraCapability
import com.bitora.android.foundation.model.BitoraDatasetStatus
import com.bitora.android.foundation.model.BitoraDeviceSnapshot
import com.bitora.android.foundation.model.BitoraDeviceStatus
import com.bitora.android.foundation.model.BitoraEdgeStatus
import com.bitora.android.foundation.model.DatasetState
import com.bitora.android.foundation.model.DeviceIdentityState
import com.bitora.android.foundation.model.EdgeConnectionState
import com.bitora.android.foundation.model.PairingState
import com.bitora.android.foundation.network.BitoraPairingClient
import com.bitora.android.foundation.network.PairedDeviceIdentity
import com.bitora.android.foundation.network.PairingDecision
import com.bitora.android.foundation.network.PairingRequest

class PairingSession(
    private val client: BitoraPairingClient? = null,
    private val store: DeviceIdentityStore? = null,
    private val deviceKind: String,
    private val requestedProfile: String,
    private val softwareVersion: String,
) {
    val code: String = PairingCodeGenerator.newCode()
    val nonce: String = PairingCodeGenerator.newNonce()

    suspend fun register(): Result<PairingState> {
        val activeClient = client ?: return Result.success(
            PairingState(code = code, expiresInLabel = "10 min", statusLabel = "PAIRING REQUIRED"),
        )
        return activeClient.registerPairing(
            PairingRequest(
                pairingCode = code,
                deviceKind = deviceKind,
                requestedProfile = requestedProfile,
                softwareVersion = softwareVersion,
                nonce = nonce,
            )
        ).map {
            PairingState(
                code = code,
                expiresInLabel = "10 min",
                statusLabel = it.decision.name,
            )
        }
    }

    suspend fun exchangeIfApproved(): Result<PairedDeviceIdentity> {
        val activeClient = client ?: return Result.failure(IllegalStateException("Pairing client not configured"))
        return activeClient.exchangePairing(code, nonce).onSuccess { identity ->
            store?.save(identity)
        }
    }
}

fun PairedDeviceIdentity.toSnapshot(): BitoraDeviceSnapshot {
    return BitoraDeviceSnapshot(
        identity = DeviceIdentityState(
            deviceId = deviceId,
            organizationId = organizationId,
            eventId = eventId,
            status = BitoraDeviceStatus.PAIRED,
            capabilities = capabilities.mapNotNull { runCatching { BitoraCapability.valueOf(it) }.getOrNull() }.toSet(),
            profile = runCatching { com.bitora.android.foundation.model.BitoraOperationProfile.valueOf(profile) }.getOrNull(),
            eventName = eventName,
            scopeLabel = scope,
            credentialTokenPreview = if (credentialToken.length >= 8) "..." + credentialToken.takeLast(4) else "***",
        ),
        edge = EdgeConnectionState(edgeUrl = edgeBaseUrl, status = BitoraEdgeStatus.ONLINE, lastSeenLabel = "Configured"),
        dataset = DatasetState(revision = datasetRevision, status = BitoraDatasetStatus.CURRENT, freshnessLabel = "Current"),
        pairing = PairingState(code = null, statusLabel = PairingDecision.APPROVED.name),
    )
}
