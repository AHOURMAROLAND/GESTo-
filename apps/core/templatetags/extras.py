from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, arg):
    try:
        if float(arg) == 0:
            return 0
        return round(float(value) / float(arg), 2)
    except (ValueError, TypeError):
        return 0


@register.filter
def percentage(value, total):
    try:
        if float(total) == 0:
            return 0
        return round(float(value) / float(total) * 100, 1)
    except (ValueError, TypeError):
        return 0


@register.simple_tag
def active_url(request, url_name):
    from django.urls import reverse
    try:
        return 'active' if request.path == reverse(url_name) else ''
    except Exception:
        return ''


@register.filter
def role_label(role_code):
    roles = {
        'DIRECTEUR': 'Directeur',
        'CENSEUR': 'Censeur',
        'PROFESSEUR': 'Professeur',
        'COMPTABLE': 'Comptable',
        'SURVEILLANT': 'Surveillant',
        'SECRETAIRE': 'Secretaire',
        'PARENT': 'Parent',
        'ELEVE': 'Eleve',
    }
    return roles.get(role_code, role_code)


@register.filter
def initiales(user):
    try:
        f = (user.first_name or '')[:1].upper()
        l = (user.last_name or '')[:1].upper()
        return f"{f}{l}" or user.username[:2].upper()
    except Exception:
        return '??'