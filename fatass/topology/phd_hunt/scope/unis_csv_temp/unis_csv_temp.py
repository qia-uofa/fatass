import fatass


class UnisCsvTemp(fatass.SingleCsv):
    rank_top = 1
    rank_bot = 100
    faculty = 'computer science'
    FIELDS = ('rank', 'name', 'state', 'url', 'people_url')

