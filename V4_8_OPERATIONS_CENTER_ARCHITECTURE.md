# V4.8 Operations Center Architecture

`OperationsCenterService` validates organization/event ownership, reads source
tables, and emits a small operational read model. Persisted alerts, incidents
and tasks are event-scoped and included in event backup/restore.

