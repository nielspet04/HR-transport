"""Explicit transport rules shared by reference routes and shift matching."""
def km_applicable(mode):
    return ' '.join((mode or '').casefold().split()) != 'trein'
