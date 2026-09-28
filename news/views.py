from django.shortcuts import render
from .models import NewsPost


def news_list(request):
    posts = NewsPost.objects.filter(published=True)
    return render(request, 'news/news_list.html', {'posts': posts})
