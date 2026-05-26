# Package marker for lib.api. Importing this loads the submodules so that
# bin/invisible-dashboard can do `from api.chat import chat_handler` after
# its sys.path insert of lib/.
from . import chat  # registers the chat submodule for bin/invisible-dashboard
