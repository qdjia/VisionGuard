from scripts.build_runtime import remove_dev_only_metadata


def test_remove_dev_only_metadata_is_scoped_to_dist_info(tmp_path) -> None:
    internal = tmp_path / "_internal"
    pytest_metadata = internal / "pytest-8.4.2.dist-info"
    pytest_package = internal / "pytest"
    torch_metadata = internal / "torch-2.11.0.dist-info"
    for path in (pytest_metadata, pytest_package, torch_metadata):
        path.mkdir(parents=True)
        (path / "marker").write_text("x", encoding="utf-8")

    removed = remove_dev_only_metadata(tmp_path)

    assert removed == ["pytest-8.4.2.dist-info"]
    assert pytest_package.is_dir()
    assert torch_metadata.is_dir()
