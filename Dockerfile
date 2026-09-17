# NGC PyTorch ships torch, CUDA, nvcc, g++ and ninja — everything the box
# kernel needs to JIT-compile on first use. It ships no LaTeX, so paper/ needs
# the block below.
FROM nvcr.io/nvidia/pytorch:26.01-py3

WORKDIR /code

# TeX Live for paper/. This set was derived by tracing every file the paper
# build actually loads back to its owning package, not guessed:
#   latex-base         pdflatex and bibtex themselves, hyperref, colortbl,
#                      mathptmx/helvet/pslatex, bm
#   latex-recommended  microtype, booktabs, float
#   latex-extra        makecell, comment, xurl, breakurl
#   pictures           tikz/pgf — including arrows.meta, which resolves at the
#                      pgf layer rather than as a tikzlibrary file of its own
#   science            algorithm, algpseudocode
#   fonts-recommended  the URW Times/Helvetica the usenix style selects
# poppler-utils supplies pdfinfo, which paper/Makefile reports page counts with.
# Roughly 0.3 GB installed. Drop this block if you do not need to build the paper.
RUN apt-get update && apt-get install -y --no-install-recommends \
      texlive-latex-base \
      texlive-latex-recommended \
      texlive-latex-extra \
      texlive-fonts-recommended \
      texlive-pictures \
      texlive-science \
      poppler-utils \
 && rm -rf /var/lib/apt/lists/*

# Install against the package metadata alone so this layer survives source edits.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[calibration]"

COPY . .

CMD ["sleep", "infinity"]
