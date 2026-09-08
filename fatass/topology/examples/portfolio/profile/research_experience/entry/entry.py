import fatass


class Entry(fatass.Tuple):
    FIELDS = ('lab', 'advisor', 'institution', 'role', 'start_time', 'end_time', 'description')
