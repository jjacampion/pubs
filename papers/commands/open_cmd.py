import subprocess

from ..color import colored
from .. import repo
from ..paper import NoDocumentFile


def parser(subparsers, config):
    parser = subparsers.add_parser('open',
            help=colored('open the paper in a pdf viewer', 'normal'))
    parser.add_argument('citekey',
            help=colored('the paper associated citekey', 'normal'))
    return parser


def command(config, ui, citekey):
    rp = repo.Repository.from_directory()
    paper = rp.paper_from_ref(citekey, fatal=True)
    try:
        filepath = paper.get_document_path()
        subprocess.Popen([config.get('papers', 'open-cmd'), filepath])
        print("%s opened." % colored(filepath, 'filepath'))
    except NoDocumentFile:
        print("%s: No document associated to this entry %s."
                % (colored('error', 'error'), colored(citekey, 'citekey')))
        exit(-1)