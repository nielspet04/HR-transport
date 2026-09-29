"""Generate an Argon2id password hash without writing the password to disk."""
from getpass import getpass
from argon2 import PasswordHasher


def main():
    password=getpass('Nieuw lokaal wachtwoord (minimaal 14 tekens): ')
    if len(password)<14:raise SystemExit('ERROR: gebruik minimaal 14 tekens.')
    confirmation=getpass('Herhaal het wachtwoord: ')
    if password!=confirmation:raise SystemExit('ERROR: de wachtwoorden verschillen.')
    hasher=PasswordHasher(time_cost=2,memory_cost=19456,parallelism=1,hash_len=32,salt_len=16)
    print('\nZet deze volledige waarde als LOCAL_AUTH_PASSWORD_HASH:')
    print(hasher.hash(password))


if __name__=='__main__':main()
