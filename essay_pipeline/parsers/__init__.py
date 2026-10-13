"""One parser module per approved source. Register new ones here."""
from . import dannymutia_medium, haikalstheory_wordpress

PARSERS = {m.NAME: m.parse for m in (haikalstheory_wordpress, dannymutia_medium)}
