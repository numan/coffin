import inspect

from django.contrib.auth import views

from coffin.shortcuts import render_to_response
from coffin.template import RequestContext, loader

exec inspect.getsource(views).replace('from django.shortcuts import render_to_response', 'from coffin.shortcuts import render_to_response')

