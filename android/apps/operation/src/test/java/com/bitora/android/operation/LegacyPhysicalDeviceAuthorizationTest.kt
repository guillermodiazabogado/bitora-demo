package com.bitora.android.operation

import com.bitora.android.foundation.network.PairedDeviceIdentity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LegacyPhysicalDeviceAuthorizationTest {
    private val physicalLegacyIdentity = PairedDeviceIdentity(
        deviceId = "lab-043c44801c",
        organizationId = 1,
        eventId = 18,
        eventName = "V5.9.1 Railway Certification",
        profile = "ACCESO RÁPIDO",
        scope = "event:18:ACCESO RÁPIDO",
        capabilities = setOf("VALIDATE_ACCESS", "SCAN_QR", "SYNC_DATASET"),
        edgeBaseUrl = "https://lab.invalid",
        datasetRevision = "LAB-A2-18-001",
        credentialToken = "redacted",
    )

    @Test
    fun scannerAuthorizationAcceptsExactLegacyPhysicalIdentity() {
        val result = authorizeAccessDevice(
            identity = physicalLegacyIdentity,
            datasetOrganizationId = 1,
            datasetEventId = 18,
            datasetProfile = "ACCESS_FAST",
            door = "main",
            zone = "general",
            configuredDirection = "ENTRY",
            requestedDirection = AccessDirection.ENTRY,
        )

        assertTrue(result.allowed)
        assertEquals("ACCESS_FAST", result.normalizedProfile)
    }

    @Test
    fun scannerAuthorizationAcceptsPersistedUnicodeLegacyIdentity() {
        val persisted = physicalLegacyIdentity.copy(
            profile = "ACCESO\u00A0RA\u0301PIDO",
            scope = "event:18:ACCESO\u00A0RA\u0301PIDO",
        )
        val result = authorizeAccessDevice(
            identity = persisted,
            datasetOrganizationId = 1,
            datasetEventId = 18,
            datasetProfile = "ACCESS_FAST",
            door = "main",
            zone = "general",
            configuredDirection = "ENTRY",
            requestedDirection = AccessDirection.ENTRY,
        )

        assertTrue(result.allowed)
        assertEquals("ACCESS_FAST", result.normalizedProfile)
    }

    @Test
    fun scannerAuthorizationStillRejectsWrongScope() {
        val wrongScope = physicalLegacyIdentity.copy(eventId = 19)
        val result = authorizeAccessDevice(
            identity = wrongScope,
            datasetOrganizationId = 1,
            datasetEventId = 18,
            datasetProfile = "ACCESS_FAST",
            door = "main",
            zone = "general",
            configuredDirection = "ENTRY",
            requestedDirection = AccessDirection.ENTRY,
        )

        assertTrue(!result.allowed)
    }
}
