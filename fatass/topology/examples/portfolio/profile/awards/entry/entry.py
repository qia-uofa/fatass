import fatass


class Entry(fatass.Tuple):
    FIELDS = ('title', 'issuer', 'date', 'description')
