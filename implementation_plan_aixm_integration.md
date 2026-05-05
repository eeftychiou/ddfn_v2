# Implementation Plan: AIXM Parser Integration

## Goal

Replace the built-in `aixm_tool.py` implementation in `ddfn_v2` with the more robust `AixmParser` library, enabling it to be installed as a dependency and used throughout the project.

## Background Analysis

### Current State: ddfn_v2 aixm_tool.py

The existing implementation in `ddfn_v2/src/ddfn_v2/util/aixm_tool.py` provides:

- **Data Classes**: `AIXMSector`, `AIXMWaypoint`, `AIXMAirport`
- **Parser Class**: `AIXMParser` with methods:
  - `extract_sectors()` → `List[AIXMSector]`
  - `extract_waypoints()` → `List[AIXMWaypoint]`
  - `extract_airports()` → `List[AIXMAirport]`
  - `extract_routes()` → `List[Dict[str, Any]]`
  - `get_fir_bbox()` → `Optional[Dict[str, float]]`
  - `parse_coordinate()` → `float`
- **Key Features**:
  - FIR bounding box calculation with 1-degree buffer
  - Coordinate parsing (DMS formats)
  - FIR-based filtering for waypoints/airports/routes
  - Parent FIR inference with hardcoded heuristics (LC→LCCC, OL→OLBB, etc.)

### Target State: AixmParser Library

The `AixmParser` library provides:

- **38 Feature Types** fully implemented (Airspace, Airport, Navaid, Route, Procedure, etc.)
- **176 Tests** passing (100% success rate)
- **Rich Data Models**: Full AIXM 4.5 feature coverage with dataclasses
- **Advanced Features**:
  - Lazy loading with caching
  - MID indexing for O(1) element lookup
  - Filtering capabilities (`AIXMFilterConfig`, `AIXMFilter`)
  - GeoJSON/KML export functionality
  - Map visualization components

### API Compatibility Analysis

| Feature | ddfn_v2 aixm_tool | AixmParser | Compatibility |
|---------|------------------|------------|---------------|
| `extract_sectors()` | Returns `List[AIXMSector]` | `get_airspaces()` returns `List[Airspace]` | BREAKING - Different return type |
| `extract_waypoints()` | Returns `List[AIXMWaypoint]` | `get_waypoints()` returns `List[Waypoint]` | BREAKING - Different return type |
| `extract_airports()` | Returns `List[AIXMAirport]` | `get_airports()` returns `List[Airport]` | BREAKING - Different return type |
| `extract_routes()` | Returns `List[Dict]` | `get_routes()` returns `List[Route]` | BREAKING - Different return type |
| `get_fir_bbox()` | Custom implementation | Not directly available | MISSING - Needs adapter |
| `parse_coordinate()` | Standalone method | `parse_coordinate()` in utils | Compatible |
| FIR filtering | Built into methods | Via `AIXMFilterConfig` | DIFFERENT - New API |

## User Review Required

**Breaking Changes Decision**

The AixmParser library uses different data models than ddfn_v2's current implementation. We have two options:

1. **Option A (Recommended)**: Create adapter/wrapper layer to maintain backward compatibility
   - Pros: Minimal changes to existing code
   - Cons: Additional maintenance overhead

2. **Option B**: Migrate all callers to use AixmParser models directly
   - Pros: Cleaner, no adapter layer
   - Cons: Requires changes in `airspace.py`, test files, and any other consumers

**Which approach do you prefer?**

**FIR Bounding Box Feature**

The AixmParser library does not have a direct equivalent to `get_fir_bbox()`. This is used in ddfn_v2 for:
- Filtering waypoints/airports by FIR
- Spatial queries

We need to either:
1. Add this feature to AixmParser (requires library modification)
2. Implement it as an adapter function in ddfn_v2

**Which approach do you prefer?**

## Proposed Changes

### Phase 1: Prepare AixmParser for Distribution

#### [NEW] AixmParser/pyproject.toml

Create packaging configuration to enable pip installation with setuptools.

#### [MODIFY] AixmParser/src/__init__.py

Update exports to include all public APIs.

### Phase 2: Create Adapter Layer in ddfn_v2

#### [NEW] ddfn_v2/src/ddfn_v2/util/aixm_adapter.py

Create an adapter layer that bridges AixmParser models to ddfn_v2's expected interface.

**Key adapter functions:**

1. **Data Class Mapping:**
   - `Airspace` → `AIXMSector` (with polygon conversion)
   - `Waypoint` → `AIXMWaypoint` (flat lat/lon)
   - `Airport` → `AIXMAirport` (flat lat/lon)
   - `Route` → `List[Dict]` (segment extraction)

2. **Missing Features to Implement:**
   - `get_fir_bbox(fir_id)` - Calculate bounding box from airspace polygons
   - `_is_in_bbox(lat, lon, bbox)` - Spatial filtering
   - FIR-based filtering for all extraction methods

3. **Method Compatibility:**
   - Maintain same signatures: `extract_sectors()`, `extract_waypoints(fir_id)`, etc.
   - Preserve coordinate parsing behavior

### Phase 3: Update ddfn_v2 Integration

#### [MODIFY] ddfn_v2/src/ddfn_v2/util/__init__.py

Update the util package to export from the adapter.

#### [MODIFY] ddfn_v2/requirements.txt

Add AixmParser as a dependency with one of these options:
- Local editable install: `-e ../AixmParser`
- Git repository: `git+https://github.com/yourorg/aixm-parser.git@v0.1.0`
- PyPI (once published): `aixm-parser>=0.1.0`

#### [DELETE] ddfn_v2/src/ddfn_v2/util/aixm_tool.py

Remove the old implementation once the adapter is verified.

### Phase 4: Update Tests

#### [MODIFY] ddfn_v2/tests/unit/test_aixm_tool.py

Update imports to use the adapter. Tests should continue to pass without modification since the adapter maintains the same interface.

### Phase 5: Update Documentation

#### [MODIFY] ddfn_v2/Architecture.md

Update the architecture documentation to reflect the new dependency.

## Open Questions

1. **Distribution Method**: How should AixmParser be distributed?
   - A) Add to PyPI (public package)
   - B) Install from Git repository
   - C) Local editable install (`pip install -e ../AixmParser`)
   - D) Git submodule

2. **FIR Bounding Box**: Should we add `get_fir_bbox()` to the AixmParser library itself?
   - A) Yes, add to library (benefits other users)
   - B) No, keep in adapter (library stays focused)

3. **Migration Strategy**: Should we eventually migrate to native AixmParser models?
   - A) Yes, deprecate adapter over time
   - B) No, keep adapter as permanent abstraction layer

## Potential Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **API Incompatibility** | High | Medium | Comprehensive adapter layer with full test coverage |
| **Performance Regression** | Medium | Low | AixmParser has caching; benchmark before/after |
| **Missing Features** | Medium | Low | Gap analysis completed; FIR bbox implemented in adapter |
| **Dependency Management** | Low | Medium | Pin versions; use lock files |
| **Test Failures** | Medium | Medium | Run full test suite; adapter maintains same interface |
| **Namespace Handling** | Low | Low | AixmParser handles namespaces; tested |

## Risk Details

### 1. API Incompatibility Risk
The AixmParser library uses different data models (e.g., `Airspace` with `Polygon` object vs `AIXMSector` with `List[Tuple]`). The adapter layer must carefully map between these representations.

**Mitigation:**
- Comprehensive unit tests for all adapter methods
- Property-based testing to verify equivalence
- Integration tests with real AIXM files

### 2. Performance Regression Risk
AixmParser has built-in caching which should improve performance, but the adapter layer adds overhead.

**Mitigation:**
- Benchmark before/after with large AIXM files
- Profile adapter methods for bottlenecks
- Consider caching at adapter layer if needed

### 3. Missing Features Risk
The `get_fir_bbox()` method is not available in AixmParser and is critical for ddfn_v2's FIR filtering.

**Mitigation:**
- Implement in adapter layer (already planned)
- Consider contributing to upstream library

### 4. Dependency Management Risk
Adding an external dependency introduces version compatibility risks.

**Mitigation:**
- Pin versions in requirements.txt
- Use lock files (requirements-lock.txt or poetry.lock)
- Test with multiple Python versions

### 5. Test Failures Risk
Existing tests may fail due to subtle behavioral differences.

**Mitigation:**
- Run full test suite before and after
- Adapter maintains exact same interface
- Property-based testing for coordinate parsing

### 6. Namespace Handling Risk
AIXM files may use XML namespaces which could be handled differently.

**Mitigation:**
- AixmParser has robust namespace handling
- Test with namespaced XML files
- Both implementations use similar approaches

## Verification Plan

### Automated Tests

1. **Unit Tests**: Run existing `test_aixm_tool.py` (should pass without modification)
2. **Integration Tests**: Run `test_fmp_sectors_api.py` and other dependent tests
3. **End-to-End**: Run full simulation scenario with AIXM loading

### Manual Verification

1. **Load AIXM File**: Verify sectors, waypoints, airports load correctly
2. **FIR Filtering**: Verify FIR-based filtering works
3. **Map Visualization**: Verify sector polygons display correctly
4. **Performance**: Compare load times with previous implementation

### Test Commands

```bash
# Run AIXM-related tests
cd c:\Users\eftyc\Antigravity\ddfn_v2
pytest tests/unit/test_aixm_tool.py -v
pytest tests/unit/test_fmp_sectors_api.py -v

# Run full test suite
pytest tests/ -v --tb=short

# Test with real AIXM file
python -c "
from ddfn_v2.util.aixm_adapter import AIXMParser
parser = AIXMParser('AIXM/BD_2025-09-30_400005921419525.xml')
sectors = parser.extract_sectors()
print(f'Loaded {len(sectors)} sectors')
waypoints = parser.extract_waypoints()
print(f'Loaded {len(waypoints)} waypoints')
"
```

## Rollback Plan

If issues are discovered:

1. Revert `requirements.txt` to remove aixm-parser dependency
2. Restore `aixm_tool.py` from git history
3. Remove `aixm_adapter.py`
4. Update `__init__.py` to export from `aixm_tool` again

## Timeline Estimate

| Phase | Estimated Time |
|-------|---------------|
| Phase 1: AixmParser Packaging | 1-2 hours |
| Phase 2: Adapter Implementation | 3-4 hours |
| Phase 3: Integration & Testing | 2-3 hours |
| Phase 4: Documentation Updates | 1 hour |
| **Total** | **7-10 hours** |

## Benefits of Migration

1. **Feature Richness**: Access to 38 AIXM feature types vs 4 in current implementation
2. **Maintainability**: Centralized AIXM parsing logic in dedicated library
3. **Test Coverage**: 176 tests vs minimal coverage in current implementation
4. **Future-Proofing**: Easier to add new AIXM features as they become available
5. **Reusability**: AixmParser can be used by other projects

## Conclusion

The migration from the built-in `aixm_tool.py` to the `AixmParser` library is feasible with an adapter layer approach. The main risks are around API compatibility and missing features, both of which can be mitigated through careful adapter design and comprehensive testing.

The recommended approach is:
1. Create an adapter layer to maintain backward compatibility
2. Package AixmParser for distribution
3. Gradually migrate to native AixmParser models if desired

Please review the open questions and provide feedback on the preferred approach.
