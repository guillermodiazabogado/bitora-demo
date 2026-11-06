package com.bitora.android.operation

import com.bitora.android.foundation.network.PairedDeviceIdentity
import org.junit.Assert.assertEquals
import org.junit.Test

class ReceptionDecisionTest {
    private val identity = PairedDeviceIdentity(
        deviceId = "reception-1",
        organizationId = 1,
        eventId = 18,
        eventName = "LAB",
        profile = "RECEPTION",
        scope = "event:18:RECEPTION",
        capabilities = setOf("CHECK_IN", "SCAN_QR", "VIEW_PARTICIPANT", "SYNC_DATASET"),
        edgeBaseUrl = "https://lab.invalid",
        datasetRevision = "LAB-A4-1",
        credentialToken = "secret",
    )

    private val payload = """{"device":{"profile":"RECEPTION"},"participants":[{"token":"BITORA:A4:VALID","event_id":18,"status":"ACTIVE","display_name":"Test Reception","checked_in":false},{"token":"BITORA:A4:DENY","event_id":18,"status":"CANCELLED","display_name":"Test Cancelled","checked_in":false}]}"""

    @Test
    fun validParticipantChecksInAndDuplicateIsDenied() {
        val allowed = evaluateReception(identity, payload, 1, 18, 2_000_000_000, "BITORA:A4:VALID", false, 1_900_000_000)
        val duplicate = evaluateReception(identity, payload, 1, 18, 2_000_000_000, "BITORA:A4:VALID", true, 1_900_000_000)
        assertEquals(AccessDecision.ALLOW, allowed.decision)
        assertEquals("CHECKED_IN", allowed.reasonCode)
        assertEquals(AccessDecision.DENY, duplicate.decision)
        assertEquals("ALREADY_CHECKED_IN", duplicate.reasonCode)
    }

    @Test
    fun rejectsInactiveWrongScopeExpiredAndUnauthorizedDevice() {
        assertEquals("INACTIVE_ACCREDITATION", evaluateReception(identity, payload, 1, 18, 2_000_000_000, "BITORA:A4:DENY", false, 1_900_000_000).reasonCode)
        assertEquals("WRONG_EVENT", evaluateReception(identity, payload, 1, 19, 2_000_000_000, "BITORA:A4:VALID", false, 1_900_000_000).reasonCode)
        assertEquals("DATASET_EXPIRED", evaluateReception(identity, payload, 1, 18, 1_800_000_000, "BITORA:A4:VALID", false, 1_900_000_000).reasonCode)
        val missingCapability = identity.copy(capabilities = setOf("SCAN_QR"))
        assertEquals("DEVICE_NOT_AUTHORIZED", evaluateReception(missingCapability, payload, 1, 18, 2_000_000_000, "BITORA:A4:VALID", false, 1_900_000_000).reasonCode)
    }
}
