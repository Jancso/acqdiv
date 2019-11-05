from acqdiv.parsers.corpus_parser import CorpusParser
from acqdiv.parsers.corpora.main.chintang.session_parser \
    import ChintangSessionParser


class ChintangCorpusParser(CorpusParser):

    def get_session_parser(self, session_path):

        temp = session_path.replace(
            self.cfg['paths']['sessions_dir'],
            self.cfg['paths']['metadata_dir'])

        metadata_path = temp.replace('.txt', '.imdi')

        return ChintangSessionParser(session_path, metadata_path)