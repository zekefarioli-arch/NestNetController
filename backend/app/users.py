"""
Manage panel users inside the container (passwords are asked for, never put on the command line):
    docker exec -it nestnet-api python -m app.users set vivi
    docker exec -it nestnet-api python -m app.users set admin     (changes the admin's password)
    docker exec -it nestnet-api python -m app.users list
    docker exec -it nestnet-api python -m app.users remove vivi
"""
import getpass
import sys

from .services import users
from .config import settings

MIN_LENGTH = 12


def main(argv):
    if len(argv) >= 1 and argv[0] == "list":
        names = sorted(users.load_users())
        print("users in the file:", ", ".join(names) or "none")
        if settings.admin_username not in names:
            print(f"the admin '{settings.admin_username}' still uses the password of .env (run: set {settings.admin_username})")
        return 0
    if len(argv) == 2 and argv[0] == "set":
        name = argv[1].strip()
        if not name or any(c.isspace() for c in name):
            print("the username cannot be empty or contain spaces")
            return 1
        password = getpass.getpass(f"New password for {name} (at least {MIN_LENGTH} characters): ")
        if len(password) < MIN_LENGTH:
            print(f"too short: use at least {MIN_LENGTH} characters")
            return 1
        if getpass.getpass("Repeat it: ") != password:
            print("the two passwords are different, nothing changed")
            return 1
        users.set_password(name, password)
        print(f"password of {name} saved; open sessions of {name} are closed")
        return 0
    if len(argv) == 2 and argv[0] == "remove":
        if argv[1] == settings.admin_username and argv[1] not in users.load_users():
            print("that is the admin of .env: change its password with `set`, or change ADMIN_USERNAME")
            return 1
        print("removed" if users.remove_user(argv[1]) else "no such user in the file")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
