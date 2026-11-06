package com.bitora.android.operation

import com.bitora.android.foundation.network.PairedDeviceIdentity
import org.junit.Assert.assertEquals
import org.junit.Test

class LeadDecisionTest {
    private val identity = PairedDeviceIdentity("lead-1", 1, 18, "LAB", "LEAD_RETRIEVAL", "event:18:LEAD_RETRIEVAL", setOf("SCAN_QR", "VIEW_PARTICIPANT", "SYNC_DATASET"), "https://lab.invalid", "LAB-A6-18-006", "secret")
    private val payload = """{"device":{"profile":"LEAD_RETRIEVAL"},"lead_participants":[{"token":"BITORA:A6:VALID","event_id":18,"status":"ACTIVE","display_name":"Test Lead","lead_consent":true},{"token":"BITORA:A6:DENY","event_id":18,"status":"ACTIVE","display_name":"No Consent","lead_consent":false}]}"""

    @Test fun validAndDuplicate() {
        assertEquals("LEAD_CAPTURED", evaluateLead(identity, payload, 1, 18, 2_000_000_000, "BITORA:A6:VALID", false, 1_900_000_000).reasonCode)
        assertEquals("ALREADY_CAPTURED", evaluateLead(identity, payload, 1, 18, 2_000_000_000, "BITORA:A6:VALID", true, 1_900_000_000).reasonCode)
    }

    @Test fun consentIsolationAndAuthorization() {
        assertEquals("CONSENT_REQUIRED", evaluateLead(identity, payload, 1, 18, 2_000_000_000, "BITORA:A6:DENY", false, 1_900_000_000).reasonCode)
        assertEquals("WRONG_EVENT", evaluateLead(identity, payload, 1, 19, 2_000_000_000, "BITORA:A6:VALID", false, 1_900_000_000).reasonCode)
        assertEquals("DATASET_EXPIRED", evaluateLead(identity, payload, 1, 18, 1_800_000_000, "BITORA:A6:VALID", false, 1_900_000_000).reasonCode)
        assertEquals("DEVICE_NOT_AUTHORIZED", evaluateLead(identity.copy(profile = "SERVICE"), payload, 1, 18, 2_000_000_000, "BITORA:A6:VALID", false, 1_900_000_000).reasonCode)
    }
}
