from .models import ChangeSet


def changeset_context(request):
    """Provides changeset context to all templates.

    This context processor provides the active and draft changesets to all templates.

    Args:
        request: The HttpRequest object.

    Returns:
        A dictionary containing the active and draft changesets.
    """
    active_changeset_id = request.session.get("active_changeset_id")
    active_changeset = None
    if active_changeset_id:
        try:
            active_changeset = ChangeSet.objects.get(id=active_changeset_id)
        except ChangeSet.DoesNotExist:
            pass

    # To prevent multiple database hits per request, we cache the draft changesets
    # on the request object itself.
    if not hasattr(request, "_draft_changesets"):
        request._draft_changesets = ChangeSet.objects.filter(status=ChangeSet.Status.DRAFT).select_related("created_by")

    return {
        "active_changeset": active_changeset,
        "draft_changesets": request._draft_changesets,
    }
