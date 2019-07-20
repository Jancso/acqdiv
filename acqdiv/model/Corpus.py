

class Corpus:

    def __init__(self):
        """Initialize the variables representing a corpus.

        corpus (str): The corpus name.
        language (str): The corpus language.
        iso_639_3 (str): The ISO language code.
        glottolog_code (str): The Glottolog language code.
        owner (str): The name of corpus owner.
        sessions (Iterable[acqdiv.model.Session.Session]): The sessions
            of the corpus.
        """
        self.corpus = ''
        self.language = ''
        self.iso_639_3 = ''
        self.glottolog_code = ''
        self.owner = ''
        self.sessions = []

        # TODO: move to right place
        self.morpheme_type = ''
