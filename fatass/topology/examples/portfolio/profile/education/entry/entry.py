import fatass


class Entry(fatass.Tuple):
    FIELDS = ('institution', 'degree', 'field_of_study', 'start_time', 'end_time', 'location', 'honors')
