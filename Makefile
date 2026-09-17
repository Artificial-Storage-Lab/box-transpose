# There is no build at the repo root. The only Makefile that does anything is
# paper/Makefile, and this forwards to it, so `make verify` works from wherever
# you happen to be standing rather than only from inside paper/.
#
# Every target here is paper/Makefile's -- see paper/README.md for what each
# one does. The one addition is `sweep`, below.
PAPER := paper

.PHONY: all defs audit verify watch clean distclean deck sweep

all defs audit verify watch clean distclean deck:
	$(MAKE) -C $(PAPER) $@

# Re-run the experiment the paper's numbers are computed from. Deliberately
# not a prerequisite of anything: raw_data/plan_sweep/ is committed, and
# regenerating measurement data is a decision, not a build step. `make verify`
# is what checks the committed data and the paper still agree.
sweep:
	python3 experiments/plan_sweep/run.py
