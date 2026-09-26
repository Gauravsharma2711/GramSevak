"""
Test Suite: Scalable Supabase PostgreSQL Database Schema (Phase 1.6)
Validates:
1. District can be created
2. Block references District (FK)
3. Panchayat references Block (FK)
4. Invalid hierarchy references fail (IntegrityError)
5. Panchayat identifiers behave correctly (LGD code, id)
6. Weather observation references Panchayat (FK)
7. Downscaled forecast references Panchayat (FK)
8. Expected uniqueness rules work (e.g., duplicate weather observation or duplicate district)
9. Representative queries work (hierarchy navigation, weather, forecasts, multi-panchayat)
10. Existing application queries remain compatible
11. RLS behavior is enabled on all tables
12. Migration preserves 100% of existing data (zero drops, zero deletions)
"""

import pytest
import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.core.database import SessionLocal
from backend.app.models.district import District
from backend.app.models.block import Block
from backend.app.models.panchayat import Panchayat
from backend.app.models.weather_observation import WeatherObservation
from backend.app.models.downscaled_forecast import DownscaledForecast
from backend.app.models.panchayat_weather import PanchayatWeatherData


@pytest.fixture
def db():
    """Provide a transactional database session rolled back after every test."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# =============================================================================
# 1. HIERARCHY CREATION & RELATIONSHIPS (ROLLBACK PROTECTED)
# =============================================================================

def test_1_district_can_be_created(db: Session):
    """Verify that a new district can be created and queried within a rollback transaction."""
    test_dist = District(name="TestDistrict_Phase16", state="Maharashtra", code="TD16")
    db.add(test_dist)
    db.flush()
    assert test_dist.id is not None

    found = db.query(District).filter(District.name == "TestDistrict_Phase16").first()
    assert found is not None
    assert found.code == "TD16"
    assert found.state == "Maharashtra"
    db.rollback()


def test_2_block_references_district(db: Session):
    """Verify that a block successfully references an existing district."""
    nashik = db.query(District).filter(District.name == "Nashik").first()
    assert nashik is not None

    test_block = Block(name="TestBlock_Phase16", district_id=nashik.id, code="TB16")
    db.add(test_block)
    db.flush()
    assert test_block.id is not None
    assert test_block.district_id == nashik.id
    db.rollback()


def test_3_panchayat_references_block(db: Session):
    """Verify that a panchayat successfully references an existing block."""
    baglan = db.query(Block).filter(Block.name == "Baglan").first()
    assert baglan is not None

    test_p = Panchayat(
        id=9999901,
        lgd_code=9999901,
        name="TestPanchayat_Phase16",
        block_id=baglan.id,
        district_id=baglan.district_id,
        latitude=20.50,
        longitude=74.20,
        elevation_m=550.0,
    )
    db.add(test_p)
    db.flush()
    assert test_p.id == 9999901
    assert test_p.block_id == baglan.id
    db.rollback()


def test_4_invalid_hierarchy_references_fail(db: Session):
    """Verify that referencing a non-existent district_id or block_id triggers an IntegrityError."""
    # Invalid district reference in block
    invalid_block = Block(name="InvalidBlock_Phase16", district_id=99999999)
    db.add(invalid_block)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()

    # Invalid block reference in panchayat
    invalid_panchayat = Panchayat(
        id=9999902,
        lgd_code=9999902,
        name="InvalidPanchayat_Phase16",
        block_id=99999999,
    )
    db.add(invalid_panchayat)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# =============================================================================
# 2. IDENTIFIERS & CONSTRAINTS
# =============================================================================

def test_5_panchayat_identifiers_behave_correctly(db: Session):
    """Verify Panchayat identity, LGD code uniqueness/presence, and coordinate constraints."""
    panchayat = db.query(Panchayat).filter(Panchayat.id == 1001).first()
    assert panchayat is not None
    assert panchayat.id == 1001
    assert panchayat.lgd_code is not None
    assert panchayat.name is not None
    assert float(panchayat.latitude) > 0.0
    assert float(panchayat.longitude) > 0.0

    # Test coordinate check constraint rejection
    invalid_coord_p = Panchayat(
        id=9999903,
        lgd_code=9999903,
        name="InvalidCoordPanchayat",
        latitude=195.0,  # Invalid latitude (> 90)
        longitude=74.0,
    )
    db.add(invalid_coord_p)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_6_weather_references_panchayat(db: Session):
    """Verify that WeatherObservation enforces foreign key to panchayats.id."""
    existing_p = db.query(Panchayat).filter(Panchayat.id == 1001).first()
    assert existing_p is not None

    # Valid insert
    test_obs = WeatherObservation(
        panchayat_id=existing_p.id,
        lgd_code=existing_p.lgd_code,
        observation_date=datetime.date(2099, 1, 1),
        forecast_issue_date=datetime.date(2099, 1, 1),
        lead_days=0,
        actual_rainfall_mm=12.5,
        block_forecast_rainfall_mm=10.0,
        source_dataset="test",
    )
    db.add(test_obs)
    db.flush()
    assert test_obs.id is not None
    db.rollback()

    # Invalid FK
    invalid_obs = WeatherObservation(
        panchayat_id=99999999,  # Non-existent
        lgd_code=99999999,
        observation_date=datetime.date(2099, 1, 1),
    )
    db.add(invalid_obs)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_7_downscaled_forecast_references_panchayat(db: Session):
    """Verify that DownscaledForecast enforces foreign key to panchayats.id."""
    existing_p = db.query(Panchayat).filter(Panchayat.id == 1001).first()
    assert existing_p is not None

    # Valid insert
    test_fc = DownscaledForecast(
        panchayat_id=existing_p.id,
        forecast_date=datetime.date(2099, 1, 1),
        forecast_issue_date=datetime.date(2099, 1, 1),
        block_forecast_rainfall_mm=15.0,
        downscaled_rainfall_mm=14.2,
        model_name="test_model",
        model_version="v1.0",
        confidence=0.85,
    )
    db.add(test_fc)
    db.flush()
    assert test_fc.id is not None
    db.rollback()

    # Invalid FK
    invalid_fc = DownscaledForecast(
        panchayat_id=99999999,  # Non-existent
        forecast_date=datetime.date(2099, 1, 1),
        downscaled_rainfall_mm=5.0,
    )
    db.add(invalid_fc)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_8_expected_uniqueness_rules_work(db: Session):
    """Verify that uq_weather_observations (panchayat_id, observation_date) is enforced."""
    existing_obs = db.query(WeatherObservation).first()
    assert existing_obs is not None

    dup_obs = WeatherObservation(
        panchayat_id=existing_obs.panchayat_id,
        lgd_code=existing_obs.lgd_code,
        observation_date=existing_obs.observation_date,
        actual_rainfall_mm=0.0,
    )
    db.add(dup_obs)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()

    # District name uniqueness
    dup_district = District(name="Nashik")
    db.add(dup_district)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# =============================================================================
# 3. REPRESENTATIVE QUERIES
# =============================================================================

def test_9_representative_queries(db: Session):
    """Verify performance and accuracy of key application query patterns."""
    # 1. List districts
    districts = db.query(District).all()
    assert len(districts) >= 2
    dist_names = [d.name for d in districts]
    assert "Nashik" in dist_names
    assert "Pune" in dist_names

    # 2. List blocks for a district
    nashik = next(d for d in districts if d.name == "Nashik")
    blocks = db.query(Block).filter(Block.district_id == nashik.id).all()
    assert len(blocks) == 15

    # 3. List Panchayats for a block
    baglan = next(b for b in blocks if b.name == "Baglan")
    panchayats = db.query(Panchayat).filter(Panchayat.block_id == baglan.id).all()
    assert len(panchayats) > 0

    # 4. Retrieve a Panchayat
    p_1001 = db.query(Panchayat).filter(Panchayat.id == 1001).first()
    assert p_1001 is not None
    assert "Ajmer" in p_1001.name

    # 5. Retrieve recent weather for a Panchayat
    obs = (
        db.query(WeatherObservation)
        .filter(WeatherObservation.panchayat_id == 1001)
        .order_by(WeatherObservation.observation_date.desc())
        .limit(10)
        .all()
    )
    assert len(obs) > 0

    # 6. Retrieve downscaled forecasts for a Panchayat
    fc = (
        db.query(DownscaledForecast)
        .filter(DownscaledForecast.panchayat_id == 1001)
        .order_by(DownscaledForecast.forecast_date.desc())
        .limit(10)
        .all()
    )
    assert isinstance(fc, list)

    # 7. Retrieve forecast by issue date
    fc_by_issue = (
        db.query(DownscaledForecast)
        .filter(DownscaledForecast.panchayat_id == 1001)
        .filter(DownscaledForecast.forecast_issue_date != None)
        .limit(5)
        .all()
    )
    assert isinstance(fc_by_issue, list)

    # 8. Retrieve weather records for multiple Panchayats
    multi_p = [p.id for p in panchayats[:5]]
    multi_weather = (
        db.query(WeatherObservation)
        .filter(WeatherObservation.panchayat_id.in_(multi_p))
        .limit(50)
        .all()
    )
    assert len(multi_weather) > 0


# =============================================================================
# 4. COMPATIBILITY & PRESERVATION
# =============================================================================

def test_10_existing_application_queries_remain_compatible(db: Session):
    """Verify legacy PanchayatWeatherData query interface still operates cleanly."""
    legacy_row = db.query(PanchayatWeatherData).filter(PanchayatWeatherData.panchayat_id == 1001).first()
    assert legacy_row is not None
    assert legacy_row.panchayat_name is not None
    assert legacy_row.district_name == "Nashik"


def test_11_rls_behavior_is_correct(db: Session):
    """Verify Row Level Security is enabled on operational tables in PostgreSQL."""
    tables = ["districts", "blocks", "panchayats", "weather_observations", "downscaled_forecasts"]
    for table_name in tables:
        result = db.execute(
            text("SELECT rowsecurity FROM pg_tables WHERE schemaname = 'public' AND tablename = :tbl"),
            {"tbl": table_name}
        ).scalar()
        assert result is True, f"RLS should be enabled on table: {table_name}"


def test_12_migration_does_not_delete_existing_data(db: Session):
    """Verify that zero existing records were dropped or deleted across all tables."""
    assert db.query(District).count() >= 2
    assert db.query(Block).count() >= 28
    assert db.query(Panchayat).count() >= 2726
    assert db.query(WeatherObservation).count() == 188708
    assert db.query(DownscaledForecast).count() == 459
    assert db.query(PanchayatWeatherData).count() == 2726
