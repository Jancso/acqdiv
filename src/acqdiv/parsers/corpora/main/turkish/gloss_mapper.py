from acqdiv.util.csvparser import parse_csv
from acqdiv.util.path import get_full_path


class TurkishGlossMapper:

    gloss_dict = parse_csv(get_full_path(
        'parsers/corpora/main/turkish/resources/gloss.csv'))

    @classmethod
    def map(cls, gloss):
        return cls.gloss_dict.get(gloss, '')
