import fatass


class Entry(fatass.Tuple):
    FIELDS = ('company', 'role', 'location', 'start_time', 'end_time', 'description')
