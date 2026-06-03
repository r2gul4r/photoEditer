import io

from PIL import Image

from app.services.metadata import read_metadata


def test_read_metadata_includes_summary_and_full_fields(tmp_path) -> None:
    image = Image.new("RGB", (16, 12), (120, 130, 140))
    exif = Image.Exif()
    exif[271] = "TestMake"
    exif[272] = "TestModel"
    exif[34855] = 320

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    path = tmp_path / "metadata.jpg"
    path.write_bytes(buffer.getvalue())

    metadata = read_metadata(path)

    assert metadata.camera == "TestMake TestModel"
    assert metadata.iso == 320
    assert any(field.key == "Make" and field.value == "TestMake" for field in metadata.fields)
    assert any(field.key == "Model" and field.value == "TestModel" for field in metadata.fields)
