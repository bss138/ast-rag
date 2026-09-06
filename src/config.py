# src/config.py
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent   # code-rag/

def load(corpus_name):
    cfg = yaml.safe_load((ROOT / "config" / "corpus.yaml").read_text())
    return cfg["corpora"][corpus_name]

def corpus_dir(name):   return ROOT / load(name)["root"]
def data_dir(name):
    d = ROOT / "data" / name
    d.mkdir(parents=True, exist_ok=True)
    return d
def index_dir(name):
    d = ROOT / "indexes" / name
    d.mkdir(parents=True, exist_ok=True)
    return d