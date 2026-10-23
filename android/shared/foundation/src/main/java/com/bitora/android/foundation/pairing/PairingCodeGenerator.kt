package com.bitora.android.foundation.pairing

import java.security.SecureRandom

object PairingCodeGenerator {
    private val random = SecureRandom()
    private val alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789".toCharArray()

    fun newCode(): String {
        val left = randomBlock()
        val right = randomBlock()
        return "BTR-$left-$right"
    }

    fun newNonce(): String {
        val bytes = ByteArray(18)
        random.nextBytes(bytes)
        return bytes.joinToString("") { "%02x".format(it) }
    }

    fun isWellFormed(code: String): Boolean {
        return Regex("^BTR-[A-Z2-9]{4}-[A-Z2-9]{4}$").matches(code)
    }

    private fun randomBlock(): String {
        return CharArray(4) { alphabet[random.nextInt(alphabet.size)] }.concatToString()
    }
}
