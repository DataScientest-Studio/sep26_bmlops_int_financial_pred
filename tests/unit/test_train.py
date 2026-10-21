"""Unit tests of how many samples train the model."""

import pytest

from forecasting.train import SAMPLES_PER_INPUT, count_training_samples

INPUTS = 8
EVALUATION_DAYS = 60
MINIMUM = SAMPLES_PER_INPUT * (INPUTS + 1)


def test_the_minimum_of_training_samples_is_accepted():
    """Exactly the samples a regression needs remain for training."""
    samples = MINIMUM + EVALUATION_DAYS
    assert count_training_samples("TEST.US", samples, INPUTS, EVALUATION_DAYS) == (
        MINIMUM
    )


def test_fewer_training_samples_than_the_minimum_are_refused():
    """One training sample short of what a regression needs is refused."""
    samples = MINIMUM + EVALUATION_DAYS - 1
    with pytest.raises(ValueError, match="TEST.US"):
        count_training_samples("TEST.US", samples, INPUTS, EVALUATION_DAYS)
