# Password hashing — bcrypt or passlib

Decision: the bcrypt package, called directly (as presented: sep26_bmlops_int_financial_pred @ Mon Oct 12, 2026 12pm - 12:30pm (CEST); listed in [`plan.md`, "Decisions"](../plan.md#decisions)). Part of the decision "API access": users and their roles live in a `users` table, and the API checks each request's user name and password against it.

## What it has to do
- Store only a hash of each password, never the password itself, so a copy of the database does not reveal anyone's password.
- Check a password given with a request against the stored hash.
- Be slow by design and salted, so stolen hashes cannot be checked against lists of common passwords at speed.
- Keep working on every Python version the project may move to.

## bcrypt package, called directly
Pros:
- Two functions: `bcrypt.hashpw(password, bcrypt.gensalt())` to store, `bcrypt.checkpw(password, stored_hash)` to check. The salt and the cost factor are stored inside the hash.
- Maintained by the Python Cryptographic Authority (the `cryptography` project), with ready-built packages for all current Python versions.
- Independent of the operating system's password functions and of Python's `crypt` module.
- Same hash format (`$2b$…`) as the course's API security exercise, so what was learned there carries over.

Cons:
- Rejects passwords longer than 72 bytes with an error; user management must limit password length.
- Works on bytes: passwords are encoded (UTF-8) before hashing.
- Argon2id is the stronger, newer algorithm (first choice of the OWASP password storage guide); bcrypt is still an accepted choice.

## passlib (the course exercise's approach)
`CryptContext(schemes=["bcrypt"])` wraps several hash algorithms behind one interface.

Pros:
- One interface for many algorithms; can mark old ones as deprecated and re-hash on login.
- The course's API security exercise uses it, so the code is familiar.

Cons:
- Unmaintained: the last release (1.7.4) dates from 2020.
- Breaks with current versions of the bcrypt package: newer releases changed what passlib reads at start-up and reject passwords longer than 72 bytes, which passlib's own start-up check sends.
- Without the bcrypt package installed — as in the course exercise — it falls back to the operating system's password functions through Python's `crypt` module, which Python 3.13 removed. The exercise works on Python 3.12 only because of that fallback.
- Its flexibility (many algorithms, migration between them) is not needed for one users table.

## Other alternatives
- Argon2id (`argon2-cffi`, or `pwdlib` as a thin interface over it): the strongest current choice and what FastAPI's own documentation now uses; one more concept the course did not teach, and the memory cost per check needs a setting.
- `hashlib.scrypt` from the standard library: no extra package; salt, parameters and the stored format have to be handled by hand.
- Werkzeug's `generate_password_hash` (the Flask exercise): pulls a Flask library into a FastAPI project.
- Plain-text passwords (the FastAPI exam): not acceptable outside an exercise.

## Decision
The bcrypt package, called directly: `hashpw` when a user is added, `checkpw` on each request. Maintained, two functions, independent of the Python version, and the hash format the course taught. passlib is left out because it is unmaintained and fails with current bcrypt releases. Argon2id is the option to switch to if the team wants the strongest algorithm; the users table stays the same, only the stored hashes change.
