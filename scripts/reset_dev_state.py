from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / 'backend' / 'data'
DATA_DIR.mkdir(exist_ok=True)
for path in DATA_DIR.glob('*.json'):
    path.unlink(missing_ok=True)
print('Reset local service data files.')
