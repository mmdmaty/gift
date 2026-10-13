from django.shortcuts import render
from .models import Poem
from django.contrib.auth.decorators import login_required


@login_required
def list_view(request):
    poems = (
        Poem.objects.filter(about=request.user)
        .prefetch_related("sounds")
        .order_by("-created_at")
    )
    return render(
        request=request,
        context={"poems": poems},
        template_name="poems/list_view.html",
    )
