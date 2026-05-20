# Changelog

## [Unreleased] — Dashboard Migration

### Added
- Plotly Dash dashboard replacing Metabase (port 3000)
- 6 interactive tabs: Overview, Revenue, Geographic, Customers, Forecast, Recommendations
- Bilingual interface (Arabic/English) for Ministry presentation
- RFM customer segmentation visualization
- Holt-Winters forecast charts with model statistics
- Print-friendly export mode
- dashboard/Dockerfile and docker-compose integration

### Removed
- Metabase service and all related configuration
- scripts/metabase_setup.py

### Changed
- Makefile "dashboard" target now opens Dash app directly
- README.md updated to reflect new dashboard architecture
- docker-compose.yml: Metabase service replaced with telecom_dashboard
