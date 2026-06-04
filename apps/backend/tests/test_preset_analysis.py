import json
from pathlib import Path
from uuid import uuid4

from app.services.preset_analysis import ingest_preset_bytes, save_default_preset_source_registry


def _test_root(name: str) -> Path:
    root = Path(__file__).resolve().parents[1] / ".tonepilot-data" / "preset-tests" / f"{name}-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _xmp_text() -> str:
    return """<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
      crs:Name="Warm Wedding Test"
      crs:PresetType="Normal"
      crs:Exposure2012="+0.35"
      crs:Contrast2012="18"
      crs:Highlights2012="-24"
      crs:Shadows2012="20"
      crs:Temperature="6200"
      crs:Tint="7"
      crs:Vibrance="14"
      crs:Saturation="-3"
      crs:HueAdjustmentOrange="-4"
      crs:SaturationAdjustmentOrange="-8"
      crs:LuminanceAdjustmentOrange="6"
      crs:ColorGradeShadowHue="215"
      crs:ColorGradeShadowSat="8" />
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end='w'?>"""


def test_ingest_lightroom_xmp_saves_profile_without_original_body() -> None:
    root = _test_root("xmp")
    save_default_preset_source_registry(root)

    response = ingest_preset_bytes(
        _xmp_text().encode("utf-8"),
        filename="warm-wedding.xmp",
        concept="free warm wedding preset",
        source_url=None,
        reference_root=root,
    )

    profile_path = root / response.profilePath
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload)

    assert payload["featureType"] == "lightroom_preset_style_profile"
    assert payload["format"] == "xmp"
    assert payload["features"]["sliderAdjustments"]["exposure"] == 0.35
    assert payload["features"]["sliderAdjustments"]["temperature"] == 700
    assert payload["features"]["hslAdjustments"]["orange"]["saturation"] == -8
    assert payload["metadata"]["originalDeleted"] is True
    assert "Warm Wedding Test" in payload["title"]
    assert "x:xmpmeta" not in serialized
