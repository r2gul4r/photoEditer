from app.utils.image_io import infer_file_type


def test_raw_file_type_detection() -> None:
    assert infer_file_type("photo.dng") == "raw"
    assert infer_file_type("photo.ARW") == "raw"
    assert infer_file_type("photo.nef") == "raw"

