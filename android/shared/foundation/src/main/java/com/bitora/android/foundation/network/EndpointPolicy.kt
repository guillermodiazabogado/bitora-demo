package com.bitora.android.foundation.network

import java.net.URI

object EndpointPolicy {
    fun isAllowed(rawUrl: String, allowLab: Boolean): Boolean {
        val uri = runCatching { URI(rawUrl.trim()) }.getOrNull() ?: return false
        val host = uri.host?.lowercase() ?: return false
        if (uri.userInfo != null || uri.query != null || uri.fragment != null) return false
        if (allowLab) {
            return uri.scheme == "https" || (uri.scheme == "http" && isLoopback(host))
        }
        return uri.scheme == "https" &&
            !isLoopback(host) &&
            !host.endsWith(".trycloudflare.com") &&
            !host.endsWith(".invalid") &&
            !host.endsWith(".example")
    }

    private fun isLoopback(host: String): Boolean =
        host == "localhost" || host == "127.0.0.1" || host == "::1"
}
