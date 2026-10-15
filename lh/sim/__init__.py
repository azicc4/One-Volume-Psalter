"""Simulated use of the one-volume book: which pages a person turns to and how the ten ribbons move, hour by hour.

  calendar.py  date → the office celebrated (General Roman Calendar, simplified precedence; GILH/UNLY)
  layout.py    the printed book: the page of every text and hour heading (book.aux + book.pdf), its sections
  office.py    one hour as an ordered list of steps (text, page, where it is announced)
  reader.py    a reader with ten ribbons turning through those steps; ribbon policies; event log and cost
  run.py       batches of simulated days, timing, the log (build/sim/) and the report (reports/simulation.md)

    python -m lh simulate [--budget-min 90] [--seed 1]
"""
