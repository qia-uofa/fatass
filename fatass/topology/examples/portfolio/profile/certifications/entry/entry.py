import fatass


class Entry(fatass.Tuple):
    FIELDS = ('name', 'issuer', 'date', 'credential_id', 'detail')
