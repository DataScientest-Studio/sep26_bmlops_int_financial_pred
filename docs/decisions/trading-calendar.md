# Trading calendar — how the system knows trading days

Decision: the exchange_calendars package (as presented: sep26_bmlops_int_financial_pred @ Mon Oct 12, 2026 12pm - 12:30pm (CEST); listed in [`plan.md`, "Decisions"](../plan.md#decisions)). Requirement "Trading calendar" (REQ-DAT-004): only trading days of the security's exchange count; weekends, public holidays and trading suspensions are not missing data.

## What the calendar has to answer
- Is a given date a trading day on this exchange? (Load and validation: a missing quote on a trading day is a gap; on a holiday it is not.)
- Which is the next trading day after the latest stored one? This is the day a forecast is for (forecast target, prediction endpoint), and it lies in the future, so it cannot come from the stored data.
- Has today's session closed yet? (Daily ingestion and replay: a day's quote is only final after the close, in the exchange's time zone.)
- Which trading days lie between two dates? (Data freshness: "trading days between the latest stored quote and the latest available one".)

## Options

### exchange_calendars
Library of exchange calendars, one per exchange, named by the exchange's standard code (MIC: XNYS for the New York Stock Exchange, XETR for Xetra, XPAR for Euronext Paris).
- Pros: answers all four questions directly (`is_session`, `next_session`, `session_close`, `sessions_in_range`); knows holidays, early closes and each exchange's time zone; a date outside its range raises an error instead of guessing; "71 exchanges in version 4.13.2; actively maintained.
- Pros: proven in a private system of a team member, used for several exchanges for daily closes.
- Cons: by default it covers 20 years back and one year ahead; a longer history needs a start date when the calendar is created, and the year ahead is extended by updating the package once a year. Unplanned suspensions (a market closed for an event) appear only after a package update.

### pandas_market_calendars
Builds on exchange_calendars and adds further calendars (futures and other markets, about 200 in total) and a schedule table per date range.
- Pros: named in the subject's bibliography; also actively maintained; schedule tables are handy for charts.
- Cons: a second layer over the same exchange calendars; for stock exchanges it adds nothing we need, and its interface differs from the library it wraps.

### Trading days from the stored data
A day with quotes is a trading day; a day without is not.
- Pros: no package; always matches the data source.
- Cons: cannot name the next trading day, which is the day every forecast is for; cannot tell a holiday from a missing delivery, which is what the requirement asks; replay cannot know when a session has closed.

### Weekdays plus a public-holiday list (`holidays` package, or own list)
- Pros: simple to understand.
- Cons: public holidays are not exchange holidays (the New York exchange trades on some public holidays and closes on others, such as Good Friday); no early closes, no time zones; an own list has to be maintained by hand.

## Decision
exchange_calendars, created with a start date that covers the full loaded history, wrapped in one small module of the project (`forecasting.trading_calendar`) that answers the four questions above. Each security in the configuration names its exchange by MIC. The package is updated once a year to extend the year ahead, and the error raised outside the covered range is surfaced, not hidden.
