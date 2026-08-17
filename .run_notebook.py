import os, sys
WS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(WS, ".pyuser", "lib", "python3.10", "site-packages"))
os.environ["ANACONDA_REPO_TOKEN"] = "dc2505be41afbeaed64e954c893575cd02a440b85fc993fb"
import nbformat
from nbclient import NotebookClient
nb = nbformat.read(os.path.join(WS, "anaconda_channel_catalog.ipynb"), as_version=4)
client = NotebookClient(nb, timeout=3600, kernel_name="python3", resources={"metadata": {"path": WS}})
client.execute()
nbformat.write(nb, os.path.join(WS, "anaconda_channel_catalog.ipynb"))
print("EXECUTION OK")
