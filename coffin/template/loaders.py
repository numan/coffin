import re
from jinja2 import loaders

from jinja2 import loaders, TemplateNotFound
from django.template.loader import BaseLoader, find_template_loader, make_origin
from django.template import TemplateDoesNotExist
from coffin.template.loader import get_template
from django.conf import settings


django_template_source_loaders = None

match_loader = re.compile(r'^(django|coffin)\.')


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


def jinja_loader_from_django_loader(django_loader, args=None):
    """Attempts to make a conversion from the given Django loader to an
    similarly-behaving Jinja loader.

    :param django_loader: Django loader module string.
    :return: The similarly-behaving Jinja loader, or None if a similar loader
        could not be found.
    """
    if not match_loader.match(django_loader):
        return None
    for substr, func in _JINJA_LOADER_BY_DJANGO_SUBSTR.iteritems():
        if substr in django_loader:
            return func(*(args or []))
    return None


def _make_jinja_app_loader():
    """Makes an 'app loader' for Jinja which acts like
    :mod:`django.template.loaders.app_directories`.
    """
    from django.template.loaders.app_directories import app_template_dirs
    return loaders.FileSystemLoader(app_template_dirs)


def _make_jinja_filesystem_loader():
    """Makes a 'filesystem loader' for Jinja which acts like
    :mod:`django.template.loaders.filesystem`.
    """
    from django.conf import settings
    return loaders.FileSystemLoader(settings.TEMPLATE_DIRS)


def _make_jinja_cached_loader(*loaders):
    """Makes a loader for Jinja which acts like
    :mod:`django.template.loaders.cached`.
    """
    return JinjaCachedLoader(
        [jinja_loader_from_django_loader(l) for l in loaders])


# Determine loaders from Django's conf.
_JINJA_LOADER_BY_DJANGO_SUBSTR = { # {substr: callable, ...}
    'app_directories': _make_jinja_app_loader,
    'filesystem': _make_jinja_filesystem_loader,
    'cached': _make_jinja_cached_loader,
    'AppLoader': _make_jinja_app_loader,
    'FileSystemLoader': _make_jinja_filesystem_loader,
}


class JinjaCachedLoader(loaders.BaseLoader):
    """A "sort of" port of of Django's "cached" template loader
    to Jinja 2. It exists primarily to support Django's full
    TEMPLATE_LOADERS syntax.

    However, note that it does not behave exactly like Django's cached
    loader: Rather than caching the compiled template, it only caches
    the template source, and recompiles the template every time. This is
    due to the way the Jinja2/Coffin loader setup works: The ChoiceLoader,
    which Coffin uses at the root to select from any of the configured
    loaders, calls the ``get_source`` method of each loader directly,
    bypassing ``load``. Our loader can therefore only hook into the process
    BEFORE template compilation.
    Caching the compiled templates by implementing ``load`` would only
    work if this loader instance were the root loader. See also the comments
    in Jinja2's BaseLoader class.

    Note that Jinja2 has an environment-wide bytecode cache (i.e. it caches
    compiled templates), that can function alongside with this class.

    Note further that Jinja2 has an environment-wide template cache (via the
    ``auto_reload`` environment option), which duplicate the functionality
    of this class entirely, and should be preferred when possible.
    """

    def __init__(self, subloaders):
        self.loader = loaders.ChoiceLoader(subloaders)
        self.template_cache = {}

    def get_source(self, environment, template):
        key = (environment, template)
        if key not in self.template_cache:
            result = self.loader.get_source(environment, template)
            self.template_cache[key] = result
        return self.template_cache[key]
