from django.shortcuts import render
from .models import Album


def gallery(request):
    albums = Album.objects.all()
    return render(request, 'gallery/gallery.html', {'albums': albums})
