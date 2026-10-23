# V4.8 Security Report

Cross-organization and cross-event reads/writes are rejected by service scope
checks plus backend RBAC. Text fields reject control characters and executable
HTML schemes. No secrets or participant private fields are placed in the read
model.

