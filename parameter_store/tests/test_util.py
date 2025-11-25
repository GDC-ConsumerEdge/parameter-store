from django.test import RequestFactory, override_settings

from parameter_store.util import reorder_homepage_dashboard


def test_reorder_homepage_dashboard():
    """
    Tests that the reorder_homepage_dashboard function correctly reorders the app_list
    based on the UNFOLD["DASHBOARD_ITEMS_ORDER"] setting.
    """
    # 1. Setup
    # Create a mock request, it's not used by the function but required by the signature.
    request = RequestFactory().get("/")
    initial_app_list = [
        {"app_label": "auth", "name": "Authentication and Authorization"},
        {"app_label": "parameter_store", "name": "Parameter Store"},
        {"app_label": "third_party", "name": "Third Party App"},
    ]
    context = {"app_list": initial_app_list}
    desired_order = ["parameter_store", "auth", "missing_app"]

    unfold_settings = {"DASHBOARD_ITEMS_ORDER": desired_order}

    # 2. Execute
    with override_settings(UNFOLD=unfold_settings):
        new_context = reorder_homepage_dashboard(request, context)

    # 3. Assert
    final_app_list = new_context["app_list"]
    # Get the order of app_labels from the result, handling None for missing apps
    final_order = [item["app_label"] if item else None for item in final_app_list]

    # The final list should match the desired order, with None for missing apps.
    assert final_order == ["parameter_store", "auth", None]

    # Check that the items are the correct dictionaries (or None for missing ones)
    assert final_app_list[0]["name"] == "Parameter Store"
    assert final_app_list[1]["name"] == "Authentication and Authorization"
    assert final_app_list[2] is None

    # The 'third_party' app should have been dropped because it's not in desired_order
    assert len(final_app_list) == len(desired_order)
