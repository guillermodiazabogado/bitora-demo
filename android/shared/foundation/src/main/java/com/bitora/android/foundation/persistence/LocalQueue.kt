package com.bitora.android.foundation.persistence

enum class QueueItemStatus {
    PENDING,
    SENDING,
    ACKNOWLEDGED,
    REJECTED,
    RETRY,
    CONFLICT,
}

data class LocalQueueItem(
    val operationId: String,
    val idempotencyKey: String,
    val correlationId: String,
    val operationType: String,
    val payloadJson: String,
    val occurredAt: String,
    val queuedAt: String,
    val retryCount: Int = 0,
    val status: QueueItemStatus = QueueItemStatus.PENDING,
    val lastError: String? = null,
    val sequence: Long = 0,
)

interface BitoraLocalQueue {
    suspend fun enqueue(item: LocalQueueItem)
    suspend fun pending(limit: Int): List<LocalQueueItem>
    suspend fun markAcknowledged(operationId: String)
    suspend fun countPending(): Int
}
