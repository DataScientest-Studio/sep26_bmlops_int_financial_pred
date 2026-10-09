"""Trading days of an exchange.

Built on exchange_calendars; exchanges are named by their Market Identifier Code
(MIC), for example XNYS for the New York Stock Exchange.
"""

from datetime import date


def is_trading_day(exchange: str, day: date) -> bool:
    """Tell whether the exchange holds a session on that day.

    @relation(REQ-DAT-004, scope=function)

    Args:
        exchange: MIC of the exchange.
        day: Calendar date.

    Returns:
        True on a trading day; False on weekends, holidays and closures.
    """
    raise NotImplementedError


def next_trading_day(exchange: str, day: date) -> date:
    """Return the first trading day after `day`.

    @relation(REQ-DAT-004, scope=function)
    @relation(REQ-MOD-001, scope=function)

    Args:
        exchange: MIC of the exchange.
        day: Calendar date; need not be a trading day.

    Returns:
        The next trading day, strictly after `day`.
    """
    raise NotImplementedError


def trading_days(exchange: str, start: date, end: date) -> list[date]:
    """List the trading days from `start` to `end`, both included.

    @relation(REQ-DAT-004, scope=function)

    Args:
        exchange: MIC of the exchange.
        start: First calendar date.
        end: Last calendar date.

    Returns:
        The trading days in order.
    """
    raise NotImplementedError
