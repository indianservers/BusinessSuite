"""Finite release selection only; grants no operational or administrator rights."""
UPCOMING_PACKS = frozenset({'retail', 'pharma', 'restaurant'})
UPCOMING_REASON = 'Upcoming: this Business Pack cannot be activated in the current release.'


def activation_reasons(pack_key):
    return [UPCOMING_REASON] if pack_key in UPCOMING_PACKS else []


def catalog_metadata(pack_key, label):
    if pack_key in UPCOMING_PACKS:
        return {'label': label + ' (Upcoming)', 'release_status': 'upcoming',
                'foundation_state': 'upcoming', 'activation_ready': False}
    return {'release_status': 'review_required'}
