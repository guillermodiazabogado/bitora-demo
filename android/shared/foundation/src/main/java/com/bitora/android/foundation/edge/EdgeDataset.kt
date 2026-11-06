package com.bitora.android.foundation.edge

import com.bitora.android.foundation.model.BitoraDatasetStatus
import com.bitora.android.foundation.model.BitoraEdgeStatus

data class EventDatasetEnvelope(
    val organizationId: Long,
    val eventId: Long,
    val revision: String,
    val schemaVersion: String,
    val generatedAt: String,
    val expiresAtEpochSeconds: Long,
    val payloadJson: String,
    val checksum: String,
    val signature: String,
    val signingKeyId: String,
)

data class DatasetVerificationResult(
    val ok: Boolean,
    val status: BitoraDatasetStatus,
    val reason: String,
)

data class EdgeRuntimeState(
    val edgeStatus: BitoraEdgeStatus,
    val datasetStatus: BitoraDatasetStatus,
    val datasetRevision: String?,
    val queuePending: Int,
    val lastHeartbeatLabel: String,
    val lastSyncLabel: String,
)
