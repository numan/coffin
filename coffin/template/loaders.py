from jinja2 import loaders, TemplateNotFound
from django.template.loader import BaseLoader, find_template_loader, make_origin
from django.template import TemplateDoesNotExist
from coffin.template.loader import get_template
from django.conf import settings
import re

django_template_source_loaders = None

class Loader(BaseLoader):
    """
    A template loader to be used
    """
    is_usable = True

    def __init__(self, *args, **kwargs):
        super(Loader, self).__init__(*args, **kwargs)

        self._disabled = set()
        self._enabled = set()

        self._disabled_templates = set(getattr(settings, 'JINJA2_DISABLED_TEMPLATES', []))

    def is_enabled(self, template_name):
        if template_name in self._disabled:
            return False
        elif template_name in self._enabled:
            return True
        else:
            # Check and update cache
            for pattern in self._disabled_templates:
                if re.match(pattern, template_name) is not None:
                    self._disabled.add(template_name)
                    return False
            else:
                self._enabled.add(template_name)
                return True

    def load_template(self, template_name, template_dirs=None):
        if template_dirs is not None:
            raise NotImplementedError('template dirs is ignored now')

        if self.is_enabled(template_name):
            try:
                template = get_template(template_name)
            except TemplateNotFound:
                raise TemplateDoesNotExist(template_name)
            return template, template.filename
        else:
            return get_django_template(template_name, template_dirs)

def get_django_template(name, dirs=None):
    global django_template_source_loaders
    if django_template_source_loaders is None:
        loaders = []
        for loader_name in settings.JINJA2_TEMPLATE_LOADERS:
            loader = find_template_loader(loader_name)
            if loader is not None:
                loaders.append(loader)
        django_template_source_loaders = tuple(loaders)

    for loader in django_template_source_loaders:
        try:
            source, display_name = loader(name, dirs)
            return (source, make_origin(display_name, loader, name, dirs))
        except TemplateDoesNotExist:
            pass
    raise TemplateDoesNotExist(name)

def jinja_loader_from_django_loader(django_loader):
    """Attempts to make a conversion from the given Django loader to an
    similarly-behaving Jinja loader.

    :param django_loader: Django loader module string.
    :return: The similarly-behaving Jinja loader, or None if a similar loader
        could not be found.
    """
    for substr, func in _JINJA_LOADER_BY_DJANGO_SUBSTR.iteritems():
        if substr in django_loader:
            return func()
    return None

class GetTemplateDirs(object):
    def __init__(self, dirs_lambda):
        self.dirs_lambda = dirs_lambda
    def __iter__(self):
        for element in self.dirs_lambda():
            yield element


def _make_jinja_app_loader():
    """Makes an 'app loader' for Jinja which acts like
    :mod:`django.template.loaders.app_directories`.
    """
    from django.template.loaders.app_directories import app_template_dirs
    loader = loaders.FileSystemLoader([])
    loader.searchpath = GetTemplateDirs(lambda: app_template_dirs)
    return loader


def _make_jinja_filesystem_loader():
    """Makes a 'filesystem loader' for Jinja which acts like
    :mod:`django.template.loaders.filesystem`.
    """
    from django.conf import settings
    loader = loaders.FileSystemLoader([])
    loader.searchpath = GetTemplateDirs(lambda: settings.TEMPLATE_DIRS)
    return loader


# Determine loaders from Django's conf.
_JINJA_LOADER_BY_DJANGO_SUBSTR = { # {substr: callable, ...}
    'app_directories': _make_jinja_app_loader,
    'filesystem': _make_jinja_filesystem_loader,
}
