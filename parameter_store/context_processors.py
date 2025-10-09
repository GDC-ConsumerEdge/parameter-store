from django.template.loader import render_to_string

from .models import ChangeSet


def custom_header_links(request):
    """Renders a changeset selector in the header.

    This context processor renders a template to display a changeset selector in the header. It also handles the logic
    for setting the active changeset in the session.

    Args:
        request: The HttpRequest object.

    Returns:
        A dictionary containing the rendered changeset selector.
    """
    active_changeset_id = request.session.get("active_changeset_id")
    active_changeset = None
    if active_changeset_id:
        try:
            active_changeset = ChangeSet.objects.get(id=active_changeset_id)
        except ChangeSet.DoesNotExist:
            pass

    draft_changesets = ChangeSet.objects.filter(status=ChangeSet.Status.DRAFT)

    context = {
        "active_changeset": active_changeset,
        "draft_changesets": draft_changesets,
    }

    return {
        "changeset_icon": render_to_string("unfold/helpers/changeset_selector.html", context),
    }
