from acqdiv.util.MorphemeMappingCSVParser import MorphemeMappingCSVParser
from acqdiv.util.util import get_full_path


class CreeGlossMapper:

    gloss_dict = MorphemeMappingCSVParser.parse(
                    get_full_path(
                        'parsers/corpora/main/cree/resources/gloss.csv'))

    @classmethod
    def map(cls, gloss):
        gloss = cls.clean_gloss(gloss)
        return cls.gloss_dict.get(gloss, '')

    @staticmethod
    def replace_gloss_connector(gloss):
        """Replace the gloss connectors.

        There are three different gloss connectors: '.', '+', ','
        ',' adds an additional specification to a gloss, e.g.
        'p,quest” (question particle)'. '+' and ',' are replaced by a dot.
        """
        return gloss.replace(',', '.').replace('+', '.')

    @classmethod
    def clean_gloss(cls, gloss):
        # gloss = cls.replace_gloss_connector(gloss)
        return gloss