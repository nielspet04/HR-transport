"""Store a local token without terminal echo or command-line/history exposure."""
import getpass
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.geocoding import TOKEN_PATH


def main():
    if not sys.stdin.isatty():
        raise SystemExit('Voer dit zelf uit in een interactieve terminal; token nooit als argument meegeven.')
    token = getpass.getpass('Mapbox-token (invoer blijft verborgen): ').strip()
    if not token.startswith(('pk.', 'sk.')) or any(c.isspace() for c in token):
        raise SystemExit('Ongeldige tokenvorm; niets opgeslagen.')
    if TOKEN_PATH.exists() and input('Bestaande lokale token vervangen? Typ ja: ').strip() != 'ja':
        raise SystemExit('Niets gewijzigd.')
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=TOKEN_PATH.parent, delete=False) as file:
        file.write(token + '\n'); temporary = Path(file.name)
    try:
        temporary.chmod(0o600)
        os.replace(temporary, TOKEN_PATH)
    finally:
        if temporary.exists():
            temporary.unlink()
    print('Token privé opgeslagen. Geen API-aanvraag uitgevoerd. Herstart het dashboard.')


if __name__ == '__main__':
    main()
