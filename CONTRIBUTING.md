# Contributing

How to set up the project for development, check your work, and get a change into
`main`. How the system is built is in [ARCHITECTURE.md]; how to install and run it is in
[DEPLOYMENT.md].

[ARCHITECTURE.md]: ARCHITECTURE.md
[DEPLOYMENT.md]: DEPLOYMENT.md

## Development setup

You need [uv], `make`, `git` and, for everything that runs the system, Docker with
Compose. Install the Python environment with the packages the project locks:

```bash
make setup      # runs uv sync --locked and creates .venv
```

Create `.env` from `.env.example` as [DEPLOYMENT.md][install] describes. If you add a
package to `pyproject.toml`, add its row to [docs/dependencies.md] and commit the
updated `uv.lock`.

[docs/dependencies.md]: docs/dependencies.md
[install]: DEPLOYMENT.md#install
[uv]: https://docs.astral.sh/uv/

## Running the tests

| Command | What it runs |
|---|---|
| `make test` | The unit tests, in parallel; no database needed |
| `make acceptance` | The acceptance and integration tests; starts the database first |
| `make contract` | The contract tests against EODHD |
| `make lint` | `ruff check`, `ruff format --check`, `pyright` and a link check of every Markdown file; needs Docker |

`make acceptance` starts the database (`make db`) first. The acceptance tests are
black-box tests of the requirements, and the integration tests run our code against the
real database. `make contract` uses your own key from `.env` and spends calls of the
free tier's daily allowance. A check the key cannot support (history that does not reach
back far enough, too few calls left today, a refused request) is skipped with its
reason. `make lint` changes no files. Its link check runs lychee, offline, from the
Docker image that `LYCHEE_IMAGE` in the `Makefile` pins, with the repository mounted
read-only and with no network. It checks the links and `#heading` anchors of every
Markdown file that Git knows about, tracked or new but not ignored.

Format your code with `uv run ruff format`. The tests take every setting from
`.env.example`, never from your shell or your `.env`; the contract tests of
`make contract` are the exception and read the EODHD key from your `.env`. The tests log
in to the database with `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_PORT` of the
template, so these three must be the same in your `.env`, because `make db` starts the
database with them. Each test worker gets its own test database. Tests never use a cloud
service and never the network, with the same exception, the contract tests. See [Test
strategy] for how the layers fit together.

[Test strategy]: ARCHITECTURE.md#test-strategy

## Tests

-   An HTTP test asserts the status first, then the body.
-   A test never compares the text of a message.
-   A test never replaces the project's own functions with stand-ins; it
    replaces only what lies outside the project (the data source) and the API's
    shared parts in `forecasting.api.dependencies`, which exist to be replaced.
-   An acceptance test checks one sentence of a requirement through the public
    interface and cites the requirement's id at the start of its docstring. A
    unit test checks a promise of a function's docstring and cites no
    requirement.
-   Test strings are in double quotes, which Ruff's formatter (`make lint`)
    holds by its default quote style. An assert carries no message.
-   A test takes every `.env` item from `.env.example`.

## The checks CI runs

Every push runs, on GitHub, the workflow in `.github/workflows/ci.yaml`: it installs uv,
then runs `make setup`, `make lint` and `make test`. Run `make lint` and `make test`
before you push. CI does not run the acceptance and integration tests, which need the
database; run `make acceptance` before you push.

## Editing the requirements

The requirements are in `docs/requirements.sdoc`, written for StrictDoc, a tool that
keeps requirements in text files and exports them as a document. Edit that file, then
regenerate the readable version:

```bash
make requirements
```

Never edit `docs/requirements.md` by hand; the next run overwrites it. Code and tests
refer to a requirement by its id only.

## Proposing and reviewing a change

-   Work from your own branch. A change reaches `main` through a pull request, which
    shows the checks of its last push. An approval is not required.
-   Commit under your own name. When you rework a teammate's code, name them in a
    `Co-authored-by:` trailer of the commit.
-   Write commit messages as Conventional Commits: `type(scope): subject`, with one
    lowercase scope and a subject in the imperative mood, for example
    `fix(compose): build the project image once`. Use the types `feat`, `fix`, `docs`,
    `test`, `refactor`, `build` and `chore`.
-   Branch protection on `main` blocks force pushes and deleting the branch.
-   Record a decision of the team in [docs/plan.md] or [docs/decisions/], as
    [docs/team.md] describes.

[docs/decisions/]: docs/decisions/
[docs/plan.md]: docs/plan.md
[docs/team.md]: docs/team.md

## Reporting an issue

Open an issue in the GitHub issue tracker of this repository. Say what you did, what you
expected and what happened, and include the reason the command or service showed. Never
include a key, a password or price data. A security problem is reported as [SECURITY.md]
describes.

[SECURITY.md]: SECURITY.md#reporting

## Code style

Every file follows [Google's style guides] for its language. Markdown lines
have at most 80 columns, as Google's Markdown guide says; Python lines have at
most 88, Ruff's default, which departs from Google's 80. This part holds only
the project's departures from the guides and its additions to them.

-   Links between repository files are relative to the file that holds them,
    such as `docs/requirements.md#how-requirements-are-checked` from a root file
    and `../README.md` from `docs/`. A link that starts with `/` breaks in VS
    Code's multi-root workspace; a relative link works on GitHub and in any
    editor, whichever folder is opened. This departs from Google's Markdown
    guide.
-   Python imports are either a module, such as `import pandas as pd`, or the
    classes and functions by name, such as
    `from sqlalchemy import Engine, text`. Both are allowed. Importing names
    departs from Google's Python guide, which imports only packages and
    modules.
-   A blank line comes before every `return` that follows other statements.
-   Functions of one kind share one shape. For example, `train_models` and
    `predict_changes` in `src/forecasting/commands.py` both go through the
    securities with one helper. A function returns its value directly when that
    fits on one line, and otherwise through a short named variable; it never
    returns a call chain split over several lines. A constructor call or a
    comprehension may span lines.
-   Path constants are at the top of the file.
-   Names use the word that the [terms] give for the thing.
-   A number in code is a named constant at the top of its file, except a
    pipeline's fixed start date. The numbers 0, 1 and -1 as steps, indices and
    zero checks, and a test's own input and expected values, stay written out.
    A closed set of answers is an enum.
-   FastAPI dependencies and Pydantic field rules go in `Annotated[...]`.
    `Field(...)` is used on its own only for `default`, `default_factory` and
    `alias`.
-   An SQL statement in Python is fixed text with bound parameters, or
    SQLAlchemy or `psycopg.sql` composes it; it is never built by string
    formatting. Ruff's rule S608 flags the usual string-built forms of `SELECT`,
    `INSERT`, `UPDATE` and `DELETE`, not every form. The author checks every
    statement, above all those S608 never detects, such as `CREATE ROLE` and
    `DROP DATABASE`.
-   In `compose.yaml` a list is written in brackets when it fits on one line,
    and with dashes otherwise.

`make lint` enforces some of these rules. Where a tool enforces a rule, this
part names the tool's settings instead of repeating the rule: Ruff's rules and
the Google docstring convention are set under `[tool.ruff.lint]` and
`[tool.ruff.lint.pydocstyle]` in `pyproject.toml`, and Pyright's scope under
`[tool.pyright]`. Ruff formats Python at its default of 88 columns, and its
import rule orders the imports. Lychee checks the links and heading anchors
between and within the Markdown files. Nothing else checks the other rules
automatically: the author checks them, and a reviewer does too when there is
one.

[Google's style guides]: https://google.github.io/styleguide/
[terms]: ARCHITECTURE.md#terms
