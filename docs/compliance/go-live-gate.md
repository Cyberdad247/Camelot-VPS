# Go-Live Gate Checklist

The Camelot-VPS Hub is not production-ready until all of the following gates are verified.

## Identity
- [ ] MFA_for_operators
- [ ] no_shared_admin_accounts
- [ ] node_and_workload_identity
- [ ] server_derived_tenant_scope

## Policy
- [ ] policy_outside_models
- [ ] manifest_bound_leases
- [ ] revocation_tested
- [ ] stale_epoch_rejection_tested

## World Tree
- [ ] Neo4j_tenant_scope_verified
- [ ] Qdrant_payload_filter_enforced
- [ ] source_quarantine_enforced
- [ ] context_packet_budget_enforced
- [ ] graph_UI_accessibility_fallback_verified

## Evidence
- [ ] receipt_chain_verified
- [ ] tamper_detection_verified
- [ ] replay_verified
- [ ] provider_webhook_signature_verified

## Safety
- [ ] VFS_path_escape_denied
- [ ] unapproved_process_denied
- [ ] unauthorized_secret_handle_denied
- [ ] external_network_without_lease_denied
- [ ] worker_cleanup_verified

## Resilience
- [ ] backup_restore_verified
- [ ] promotion_fencing_verified
- [ ] authority_epoch_verified
- [ ] failback_drill_completed
