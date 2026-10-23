package com.bitora.android.foundation.edge

import com.bitora.android.foundation.model.BitoraDatasetStatus
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

class DatasetVerifier(private val trustedLabKey: String = "BITORA-A2-LAB-SIGNING-KEY") {
    fun verify(envelope: EventDatasetEnvelope, expectedOrganizationId: Long, expectedEventId: Long, activeRevision: String? = null): DatasetVerificationResult {
        if (envelope.organizationId != expectedOrganizationId) return DatasetVerificationResult(false, BitoraDatasetStatus.INVALID, "wrong_org")
        if (envelope.eventId != expectedEventId) return DatasetVerificationResult(false, BitoraDatasetStatus.INVALID, "wrong_event")
        if (envelope.expiresAtEpochSeconds <= System.currentTimeMillis() / 1000L) return DatasetVerificationResult(false, BitoraDatasetStatus.EXPIRED, "expired")
        val checksum = sha256(envelope.payloadJson)
        if (checksum != envelope.checksum) return DatasetVerificationResult(false, BitoraDatasetStatus.INVALID, "corrupt_dataset")
        val signature = hmac("${envelope.organizationId}|${envelope.eventId}|${envelope.revision}|${envelope.checksum}|${envelope.expiresAtEpochSeconds}")
        if (signature != envelope.signature) return DatasetVerificationResult(false, BitoraDatasetStatus.INVALID, "invalid_signature")
        if (activeRevision != null && envelope.revision < activeRevision) return DatasetVerificationResult(false, BitoraDatasetStatus.STALE, "downgrade")
        return DatasetVerificationResult(true, BitoraDatasetStatus.CURRENT, "valid")
    }

    private fun sha256(value: String): String {
        return MessageDigest.getInstance("SHA-256").digest(value.toByteArray()).joinToString("") { "%02x".format(it) }
    }

    private fun hmac(value: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(trustedLabKey.toByteArray(), "HmacSHA256"))
        return mac.doFinal(value.toByteArray()).joinToString("") { "%02x".format(it) }
    }
}
