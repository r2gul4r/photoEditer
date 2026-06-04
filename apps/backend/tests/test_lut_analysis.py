import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.services.lut_analysis import (
    LutAnalysisError,
    LutSourcePolicyError,
    apply_lut,
    ingest_lut_bytes,
    ingest_lut_url,
    parse_cube_lut,
)


def _test_root(name: str) -> Path:
    root = Path(__file__).resolve().parents[1] / ".tonepilot-data" / "lut-tests" / f"{name}-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _cube_text(*, red_gain: float = 0.08, blue_loss: float = 0.06) -> str:
    rows: list[str] = []
    for blue in (0.0, 1.0):
        for green in (0.0, 1.0):
            for red in (0.0, 1.0):
                rows.append(f"{min(1.0, red + red_gain):.6f} {green:.6f} {max(0.0, blue - blue_loss):.6f}")
    return "\n".join(
        [
            'TITLE "Warm Test LUT"',
            "LUT_3D_SIZE 2",
            "DOMAIN_MIN 0 0 0",
            "DOMAIN_MAX 1 1 1",
            *rows,
            "",
        ]
    )


def test_parse_cube_lut_and_interpolate() -> None:
    lut = parse_cube_lut(_cube_text())
    mapped = apply_lut(lut, [[0.5, 0.5, 0.5]])[0]

    assert lut.size == 2
    assert lut.title == "Warm Test LUT"
    assert mapped[0] > mapped[2]


def test_rejects_unsupported_cube_shapes() -> None:
    with pytest.raises(LutAnalysisError, match="1D"):
        parse_cube_lut("LUT_1D_SIZE 2\n0 0 0\n1 1 1\n")


def test_parse_cube_lut_accepts_input_range_metadata() -> None:
    lut = parse_cube_lut("LUT_3D_SIZE 2\nLUT_3D_INPUT_RANGE 0 1\n" + "\n".join(["0 0 0"] * 8))

    assert lut.size == 2


def test_ingest_lut_bytes_saves_non_invertible_profile_and_deletes_original() -> None:
    root = _test_root("byte-ingest")
    response = ingest_lut_bytes(
        _cube_text().encode("utf-8"),
        filename="warm-test.cube",
        concept="sunset warmth",
        license_name="user-provided",
        reference_root=root,
    )

    profile_path = root / response.profilePath
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload)

    assert profile_path.exists()
    assert response.profile.metadata.originalDeleted is True
    assert not list((root / "luts" / "tmp").glob("*.cube"))
    assert payload["featureType"] == "non_invertible_lut_style_profile"
    assert payload["metadata"]["sha256"]
    assert payload["metadata"]["importedAt"]
    assert payload["metadata"]["originalDeleted"] is True
    assert "warm" in payload["derivedTags"]
    assert "lookup_grid" not in serialized
    assert "LUT_3D_SIZE" not in serialized


def test_url_ingest_requires_allowlisted_direct_download_source() -> None:
    root = _test_root("blocked-url")
    with pytest.raises(LutSourcePolicyError, match="not in the allowlisted"):
        ingest_lut_url(
            "https://example.com/free/warm.cube",
            reference_root=root,
            downloader=lambda _url: _cube_text().encode("utf-8"),
        )


def test_url_ingest_uses_allowlisted_source_metadata_without_network() -> None:
    root = _test_root("allowed-url")
    registry_dir = root / "luts"
    registry_dir.mkdir(parents=True)
    (registry_dir / "source_registry.json").write_text(
        json.dumps(
            {
                "version": 1,
                "sources": [
                    {
                        "id": "example-free-luts",
                        "name": "Example Free LUTs",
                        "status": "allow",
                        "sourceType": "allowed_public_lut",
                        "urlPrefixes": ["https://example.com/free/"],
                        "license": "CC0-1.0",
                        "directDownloadAllowed": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    response = ingest_lut_url(
        "https://example.com/free/warm.cube",
        concept="golden hour",
        reference_root=root,
        downloader=lambda _url: _cube_text().encode("utf-8"),
    )

    assert response.profile.metadata.sourceUrl == "https://example.com/free/warm.cube"
    assert response.profile.metadata.sourceType == "allowed_public_lut"
    assert response.profile.metadata.status == "allow"
    assert response.profile.metadata.license == "CC0-1.0"
    assert response.profile.metadata.downloadedAt
    assert response.profile.metadata.importedAt is None
