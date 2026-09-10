from __future__ import annotations

from conftest import create_category, rename_category


def test_category_create_list_and_rename_expose_versions_and_etags(client, token_a):
    created = create_category(client, token_a, "  Trail   Running ")

    assert created.status_code == 201
    assert created.headers["ETag"] == '"1"'
    assert created.json()["name"] == "Trail Running"
    assert created.json()["version"] == 1

    listed = client.get("/api/v1/categories", headers={"Authorization": f"Bearer {token_a}"})
    assert [item["name"] for item in listed.json()["items"]] == ["Trail Running"]

    renamed = rename_category(client, token_a, created.json()["id"], '"1"', "Road Running")
    assert renamed.status_code == 200
    assert renamed.headers["ETag"] == '"2"'
    assert renamed.json()["version"] == 2


def test_category_duplicate_is_case_and_space_insensitive_per_user(client, token_a):
    create_category(client, token_a, "Trail   Running")

    response = create_category(client, token_a, " trail running ")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "category_name_exists"


def test_same_category_name_is_allowed_for_different_users(client, token_a, token_b):
    assert create_category(client, token_a, "Running").status_code == 201
    assert create_category(client, token_b, " running ").status_code == 201


def test_category_rename_requires_if_match(client, token_a):
    category = create_category(client, token_a).json()

    response = rename_category(client, token_a, category["id"], None)

    assert response.status_code == 428
    assert response.json()["error"]["code"] == "precondition_required"


def test_category_stale_if_match_returns_412(client, token_a):
    category = create_category(client, token_a).json()
    rename_category(client, token_a, category["id"], '"1"', "First")

    stale = rename_category(client, token_a, category["id"], '"1"', "Second")

    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "stale_version"


def test_category_rename_duplicate_returns_conflict(client, token_a):
    first = create_category(client, token_a, "Running").json()
    create_category(client, token_a, "Reading")

    response = rename_category(client, token_a, first["id"], '"1"', " reading ")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "category_name_exists"


def test_category_rename_malformed_id_returns_validation_error(client, token_a):
    response = rename_category(client, token_a, "not-a-uuid", '"1"', "Running")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


def test_cross_user_category_rename_is_safe_404(client, token_b, category_a):
    response = rename_category(client, token_b, category_a["id"], '"1"', "Stolen")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"
