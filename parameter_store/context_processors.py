from django.template.loader import render_to_string

from .models import ChangeSet


def custom_header_links(request):
    """
    Adds custom links to the userlinks header area.
    """
    active_changeset_id = request.session.get("active_changeset_id")
    active_changeset = None
    if active_changeset_id:
        try:
            active_changeset = ChangeSet.objects.get(id=active_changeset_id)
        except ChangeSet.DoesNotExist:
            pass

    draft_changesets = ChangeSet.objects.filter(status=ChangeSet.Status.DRAFT)

    if request.GET.get("active_changeset"):
        request.session["active_changeset_id"] = request.GET.get("active_changeset")

    context = {
        "active_changeset": active_changeset,
        "draft_changesets": draft_changesets,
    }

    return {
        "changeset_icon": render_to_string("unfold/helpers/changeset_selector.html", context),
    }
