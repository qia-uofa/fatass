import fatass


class Entry(fatass.Tuple):
    FIELDS = ('title', 'venue', 'date', 'authors', 'url')
