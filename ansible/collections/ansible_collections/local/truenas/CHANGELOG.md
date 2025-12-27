# Changelog

All notable changes to this collection will be documented in this file.

## [0.2.0] - 2025-12-27

### Added

- `pool_scrub` module for pool scrub tasks
- `pool_snapshottask` module for periodic snapshot tasks
- `service` module for service enable/start/stop
- `sharing_nfs` module for NFS shares
- `sharing_smb` module for SMB shares
- `smart_test` module for SMART test schedules
- Shared `MidcltClient` utility in `plugin_utils/midclt.py` for typed midclt operations

### Changed

- Refactored `initshutdownscript` to use shared `MidcltClient`
- Moved all business logic from module stubs to action plugins (controller-side execution)

## [0.1.0] - 2024-12-26

### Added

- Initial release
- `initshutdownscript` module for managing TrueNAS init/shutdown scripts
