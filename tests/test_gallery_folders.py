"""Gallery folder CRUD + plugin choices endpoint."""

from __future__ import annotations

import io
from pathlib import Path

from flask.testing import FlaskClient
from PIL import Image


def _png_bytes(color: str = "red") -> bytes:
    img = Image.new("RGB", (10, 10), color=color)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def test_list_empty(client: FlaskClient) -> None:
    body = client.get("/plugins/gallery/api/folders").get_json()
    assert body == []


def test_create_folder_and_list(client: FlaskClient, tmp_path: Path) -> None:
    res = client.post(
        "/plugins/gallery/api/folders", json={"name": "vacation"}
    )
    assert res.status_code == 200
    listing = client.get("/plugins/gallery/api/folders").get_json()
    names = [f["name"] for f in listing]
    assert "vacation" in names
    # Folder is empty so far
    folder = next(f for f in listing if f["name"] == "vacation")
    assert folder["image_count"] == 0
    # And it's been created on disk
    assert (tmp_path / "data" / "plugins" / "gallery" / "vacation").is_dir()


def test_create_rejects_bad_name(client: FlaskClient) -> None:
    # The server lowercases input — "Vacation" becomes "vacation". So we
    # only test characters the regex actively rejects.
    for bad in ["with spaces", "with/slash", "..parent", "", "_leading_underscore"]:
        res = client.post(
            "/plugins/gallery/api/folders", json={"name": bad}
        )
        assert res.status_code == 400, f"expected 400 for {bad!r}"


def test_create_lowercases_input(client: FlaskClient) -> None:
    res = client.post("/plugins/gallery/api/folders", json={"name": "Vacation"})
    assert res.status_code == 200
    assert res.get_json()["name"] == "vacation"


def test_create_rejects_duplicate(client: FlaskClient) -> None:
    client.post("/plugins/gallery/api/folders", json={"name": "dup"})
    res = client.post("/plugins/gallery/api/folders", json={"name": "dup"})
    assert res.status_code == 409


def test_delete_folder(client: FlaskClient, tmp_path: Path) -> None:
    client.post("/plugins/gallery/api/folders", json={"name": "trash-me"})
    res = client.delete("/plugins/gallery/api/folders/trash-me")
    assert res.status_code == 204
    assert not (tmp_path / "data" / "plugins" / "gallery" / "trash-me").exists()


def test_delete_root_forbidden(client: FlaskClient) -> None:
    res = client.delete("/plugins/gallery/api/folders/_root")
    assert res.status_code == 403


def test_upload_then_list_includes_image(client: FlaskClient, tmp_path: Path) -> None:
    client.post("/plugins/gallery/api/folders", json={"name": "uploads"})
    res = client.post(
        "/plugins/gallery/api/folders/uploads/images",
        data={"file": (io.BytesIO(_png_bytes()), "fox.png")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    body = res.get_json()
    assert "fox.png" in body["saved"]
    listing = client.get("/plugins/gallery/api/folders").get_json()
    folder = next(f for f in listing if f["name"] == "uploads")
    assert folder["image_count"] == 1
    assert any(img["name"] == "fox.png" for img in folder["images"])


def test_upload_skips_disallowed_extension(client: FlaskClient) -> None:
    client.post("/plugins/gallery/api/folders", json={"name": "skip"})
    res = client.post(
        "/plugins/gallery/api/folders/skip/images",
        data={"file": (io.BytesIO(b"plain text"), "evil.txt")},
        content_type="multipart/form-data",
    )
    body = res.get_json()
    assert "evil.txt" in body["skipped"]
    assert body["saved"] == []


def test_delete_image(client: FlaskClient) -> None:
    client.post("/plugins/gallery/api/folders", json={"name": "rm"})
    client.post(
        "/plugins/gallery/api/folders/rm/images",
        data={"file": (io.BytesIO(_png_bytes("blue")), "blue.png")},
        content_type="multipart/form-data",
    )
    res = client.delete("/plugins/gallery/api/folders/rm/images/blue.png")
    assert res.status_code == 204
    listing = client.get("/plugins/gallery/api/folders").get_json()
    folder = next(f for f in listing if f["name"] == "rm")
    assert folder["image_count"] == 0


def test_serve_image(client: FlaskClient) -> None:
    client.post("/plugins/gallery/api/folders", json={"name": "serve"})
    client.post(
        "/plugins/gallery/api/folders/serve/images",
        data={"file": (io.BytesIO(_png_bytes("green")), "go.png")},
        content_type="multipart/form-data",
    )
    res = client.get("/plugins/gallery/folders/serve/go.png")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/")


def test_choices_endpoint_lists_folders(client: FlaskClient) -> None:
    client.post("/plugins/gallery/api/folders", json={"name": "alpha"})
    client.post("/plugins/gallery/api/folders", json={"name": "beta"})
    res = client.get("/api/plugins/gallery/choices/folders")
    assert res.status_code == 200
    body = res.get_json()
    values = [c["value"] for c in body]
    assert "alpha" in values
    assert "beta" in values


def test_choices_unknown_name_returns_empty(client: FlaskClient) -> None:
    res = client.get("/api/plugins/gallery/choices/unknown")
    assert res.status_code == 200
    assert res.get_json() == []


def test_choices_missing_plugin_404s(client: FlaskClient) -> None:
    res = client.get("/api/plugins/no-such-plugin/choices/folders")
    assert res.status_code == 404


def test_admin_pages_endpoint_includes_gallery_and_todo(client: FlaskClient) -> None:
    body = client.get("/api/plugins/admin-pages").get_json()
    ids = {p["id"] for p in body}
    assert "gallery" in ids
    assert "todo" in ids


def test_create_external_folder_lists_images(client: FlaskClient, tmp_path: Path) -> None:
    """External folders point at an existing host directory and surface its images."""
    ext = tmp_path / "external_pics"
    ext.mkdir()
    (ext / "a.png").write_bytes(_png_bytes("red"))
    (ext / "b.png").write_bytes(_png_bytes("blue"))
    (ext / "ignore.txt").write_bytes(b"not an image")

    res = client.post(
        "/plugins/gallery/api/folders",
        json={"name": "extpics", "external_path": str(ext)},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["external_path"] == str(ext.resolve())
    assert body["image_count"] == 2

    listing = client.get("/plugins/gallery/api/folders").get_json()
    folder = next(f for f in listing if f["name"] == "extpics")
    assert folder["external_path"] == str(ext.resolve())
    names = {img["name"] for img in folder["images"]}
    assert names == {"a.png", "b.png"}


def test_external_folder_rejects_uploads(client: FlaskClient, tmp_path: Path) -> None:
    ext = tmp_path / "readonly_pics"
    ext.mkdir()
    client.post(
        "/plugins/gallery/api/folders",
        json={"name": "ro", "external_path": str(ext)},
    )
    res = client.post(
        "/plugins/gallery/api/folders/ro/images",
        data={"file": (io.BytesIO(_png_bytes()), "blocked.png")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 403
    assert not (ext / "blocked.png").exists()


def test_external_folder_rejects_image_delete(client: FlaskClient, tmp_path: Path) -> None:
    ext = tmp_path / "ext_keep"
    ext.mkdir()
    (ext / "keep.png").write_bytes(_png_bytes("yellow"))
    client.post(
        "/plugins/gallery/api/folders",
        json={"name": "keepers", "external_path": str(ext)},
    )
    res = client.delete("/plugins/gallery/api/folders/keepers/images/keep.png")
    assert res.status_code == 403
    assert (ext / "keep.png").exists()


def test_delete_external_folder_does_not_touch_files(
    client: FlaskClient, tmp_path: Path
) -> None:
    ext = tmp_path / "external_keep"
    ext.mkdir()
    (ext / "important.png").write_bytes(_png_bytes("green"))
    client.post(
        "/plugins/gallery/api/folders",
        json={"name": "ephemeral", "external_path": str(ext)},
    )
    res = client.delete("/plugins/gallery/api/folders/ephemeral")
    assert res.status_code == 204
    # Folder entry gone from listing, but the underlying directory + files survive.
    listing = client.get("/plugins/gallery/api/folders").get_json()
    assert all(f["name"] != "ephemeral" for f in listing)
    assert (ext / "important.png").exists()


def test_create_external_rejects_missing_path(client: FlaskClient, tmp_path: Path) -> None:
    res = client.post(
        "/plugins/gallery/api/folders",
        json={"name": "nope", "external_path": str(tmp_path / "does_not_exist")},
    )
    assert res.status_code == 400


def test_create_external_rejects_file_path(client: FlaskClient, tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("hello")
    res = client.post(
        "/plugins/gallery/api/folders",
        json={"name": "filey", "external_path": str(f)},
    )
    assert res.status_code == 400


def test_thumbnail_url_is_in_listing(client: FlaskClient) -> None:
    client.post("/plugins/gallery/api/folders", json={"name": "thumbs"})
    client.post(
        "/plugins/gallery/api/folders/thumbs/images",
        data={"file": (io.BytesIO(_png_bytes()), "a.png")},
        content_type="multipart/form-data",
    )
    listing = client.get("/plugins/gallery/api/folders").get_json()
    folder = next(f for f in listing if f["name"] == "thumbs")
    img = folder["images"][0]
    assert img["thumb_url"].endswith("/thumb")
    assert img["url"].endswith("/a.png")


def test_thumbnail_endpoint_returns_jpeg_and_caches(
    client: FlaskClient, tmp_path: Path
) -> None:
    client.post("/plugins/gallery/api/folders", json={"name": "tcache"})
    client.post(
        "/plugins/gallery/api/folders/tcache/images",
        data={"file": (io.BytesIO(_png_bytes("blue")), "b.png")},
        content_type="multipart/form-data",
    )
    res = client.get("/plugins/gallery/folders/tcache/b.png/thumb")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/jpeg")
    assert "max-age=31536000" in res.headers["cache-control"]
    # Cache file landed on disk.
    cache_dir = tmp_path / "data" / "plugins" / "gallery" / ".thumb_cache"
    assert cache_dir.is_dir()
    assert any(p.suffix == ".jpg" for p in cache_dir.iterdir())


def test_thumbnail_endpoint_404_for_missing_image(client: FlaskClient) -> None:
    client.post("/plugins/gallery/api/folders", json={"name": "empty"})
    res = client.get("/plugins/gallery/folders/empty/missing.png/thumb")
    assert res.status_code == 404


def test_choices_marks_external_folders(client: FlaskClient, tmp_path: Path) -> None:
    ext = tmp_path / "marked"
    ext.mkdir()
    (ext / "img.png").write_bytes(_png_bytes("red"))
    client.post("/plugins/gallery/api/folders", json={"name": "internal"})
    client.post(
        "/plugins/gallery/api/folders",
        json={"name": "external", "external_path": str(ext)},
    )
    body = client.get("/api/plugins/gallery/choices/folders").get_json()
    by_value = {c["value"]: c["label"] for c in body}
    assert "↗" in by_value["external"]
    assert "↗" not in by_value["internal"]
