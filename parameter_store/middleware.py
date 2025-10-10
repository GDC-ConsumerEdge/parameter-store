from django.http import HttpResponseRedirect


def changeset_middleware(get_response):
    def middleware(request):
        if "active_changeset" in request.GET:
            request.session["active_changeset_id"] = request.GET.get("active_changeset")
            return HttpResponseRedirect(request.path)
        response = get_response(request)
        return response

    return middleware
