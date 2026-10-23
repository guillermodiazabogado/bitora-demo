package com.bitora.android.foundation.network

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EndpointPolicyTest {
    @Test
    fun productionAcceptsOnlyStableHttpsEndpoints() {
        assertTrue(EndpointPolicy.isAllowed("https://edge.bitora.app", allowLab = false))
        assertFalse(EndpointPolicy.isAllowed("", allowLab = false))
        assertFalse(EndpointPolicy.isAllowed("http://edge.bitora.app", allowLab = false))
        assertFalse(EndpointPolicy.isAllowed("https://demo.trycloudflare.com", allowLab = false))
        assertFalse(EndpointPolicy.isAllowed("https://api.example", allowLab = false))
        assertFalse(EndpointPolicy.isAllowed("https://user:pass@edge.bitora.app", allowLab = false))
    }

    @Test
    fun labAllowsHttpsTunnelsAndLoopbackHttp() {
        assertTrue(EndpointPolicy.isAllowed("https://demo.trycloudflare.com", allowLab = true))
        assertTrue(EndpointPolicy.isAllowed("http://127.0.0.1:8831", allowLab = true))
        assertFalse(EndpointPolicy.isAllowed("http://remote-host.test", allowLab = true))
    }
}
