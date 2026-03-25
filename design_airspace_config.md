# Airspace Configuration Design Specification

This document provides a baseline design for the Airspace Configuration tab in the FMP Dashboard. It ensures consistency across future bug fixes and feature enhancements.

## 1. Functional Overview
The Airspace Configuration tab is the primary interface for defining a node's area of responsibility (AoR). It allows users to:
1. Load airspace definitions from an AIXM file.
2. Select an FIR from the AIXM source.
3. Define a subset of sectors or full FIR responsibility.
4. Select airports to be managed as virtual 3D sectors.
5. Set baseline capacity and measurement window parameters.
6. Save and apply the configuration to the node.

## 2. User Interface Layout

### 2.1 Sidebar: Configuration Controls
- **AIXM Source**: Text input for file path + "Load AIXM" button.
- **FIR Selection**: Dropdown menu populated after loading AIXM.
- **Node Settings**:
  - **Baseline Capacity**: Number input (default 40).
  - **Node Display Name**: Text input for the configuration name.
  - **Measurement Window**: Number input for sliding window size (minutes).
- **Persistence**: "Load Saved Configuration" dropdown and "Save & Apply Airspace Config" button.

### 2.2 Main Panels (Grid)

#### A. Sector List Panel
- **Select / Unselect All**: A sticky header containing a master checkbox to toggle all sectors.
- **Sector Entry**:
  - Checkbox for inclusion.
  - Sector ID and Name.
  - **Flight Level Overrides**: Inputs for Min/Max FL, initialized from AIXM but user-adjustable.
- **Visual Feedback**: Selection state is immediately reflected on the configuration map.

#### B. Airport List Panel
- **Select / Unselect All**: Master checkbox for airports.
- **Airport Entry**: Checkbox + Airport ID (ICAO) + Name.
- **Behavior**: Selecting an airport creates a circular virtual sector in the backend.

#### C. Configuration Map
- A Leaflet map showing the boundary polygons of all sectors in the selected FIR.
- Highlighted polygons for currently selected/active sectors.

## 3. Implementation Logic

### 3.1 Data Flow: Initialization
1. `initWorkspace()` fetches node `/metadata` to set `window.CURRENT_RESPONSIBILITY`.
2. `initConfigTab()` fetches `/api/config/aixm_source` to pre-fill the form.
3. `loadAixmSource()` fetches available FIRs.
4. `loadFirSectors()` fetches sectors and calls `renderConfigSectors()`.
5. `renderConfigSectors()` merges `data.sectors` with `window.CURRENT_RESPONSIBILITY` to set the initial `checked` state and FL values.

### 3.2 Master Checkbox (Select All)
- **State Logic**: 
  - `checked`: If all visible items are checked.
  - `unchecked`: If no visible items are checked.
  - `indeterminate`: If some (but not all) items are checked.
- **Action**: Toggling the master checkbox checks/unchecks all visible items and triggers a map update.

### 3.3 Data Persistence: Reference-Based Model
To ensure versatility and simplicity, the FMP node configuration does not store full geometries or redundant AIXM metadata. Instead, it stores:
1. **AIXM Source Reference**: File path and FIR ID.
2. **Responsibility References**: Lists of IDs for sectors and airports.
3. **Local Overrides**: User-specified Flight Level (FL) ranges or baseline capacities that differ from AIXM defaults.

### 3.4 Initialization Sequence (Extended)
1. `FMPNode` starts and reads its local `{node_id}.json`.
2. It extracts the `aixm_source_file`.
3. It calls `load_aixm_to_registry(file_path)`, which populates the global `WAYPOINTS`, `AIRWAYS`, and `SECTORS` databases.
4. The node then iterates its `sector_configs` (IDs) and retrieves the corresponding geometry and name from the global registry to initialize its active `SectorCapacity` objects.
5. This pattern ensures the node has the **full FIR context** (for trajectory lookup and visualization) while only being **responsible** for its sub-selection.

## 4. API & Data Structures

### 4.1 Apply Configuration Payload
- **API Endpoint**: `POST /api/config/apply_aixm`
- **Simplified Payload**:
  ```json
  {
    "file_path": "...",
    "fir_id": "...",
    "config_name": "...",
    "sectors": [
      {"id": "LCCCWU", "fl_lower": 100, "fl_upper": 450}
    ],
    "airports": [
      {"id": "LCPH", "name": "Paphos", "lat": 34.71, "lon": 32.48}
    ],
    "window_size": 120,
    "baseline_capacity": 40
  }
  ```

### 4.2 On-Disk Configuration format
The persistent `{node_id}.json` reflects the payload above, ensuring the file remains small even for complex FIRs.

## 4. Visual Styles
- **Glassmorphism**: Panels use `backdrop-filter: blur(10px)` and transparent backgrounds.
- **Sticky Headers**: "Select All" headers use `sticky-top` to remain visible during scrolling.
- **Interactive States**: Hover effects on list items and transition animations for checkbox state changes.
