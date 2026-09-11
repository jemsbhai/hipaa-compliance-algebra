# IEEE HealthCom 2026 — Paper 1

**Title:** Privacy-Preserving Confidence-Aware FHIR R4 Exchange: A HIPAA Compliance Algebra Grounded in Subjective Logic

**Venue:** IEEE International Conference on E-health Networking, Application & Services (HealthCom 2026)  
**Location:** New York City, October 19–21, 2026  
**Deadline:** ~July 15, 2026  
**Format:** 6+2 pages, IEEE two-column, 10pt

## Project Structure

```
healthcom2026paper1/
├── PAPER_PLAN.md          # Master plan document
├── FINDINGS.md            # Experimental findings (append-only)
├── README.md              # This file
├── paper/                 # LaTeX source
│   ├── main.tex
│   └── refs.bib
├── experiments/
│   ├── EH1/               # HIPAA operator property verification
│   ├── EH2/               # Clinical compliance pipeline
│   ├── EH3/               # HE proof-of-concept
│   ├── EH4/               # Binary tool comparison
│   ├── tests/             # RED-phase tests
│   └── results/           # JSON output
└── figures/               # TikZ/pgfplots figures
```

## Dependencies

- jsonld-ex >= 0.7.3 (library under development)
- hypothesis >= 6.0 (property-based testing)
- numpy >= 1.24 (statistics)
- tenseal >= 0.3.0 (CKKS homomorphic encryption) — for EH3

## Related Papers

- FLAIRS 2026: JSON-LD 1.2 gap analysis (published)
- NeurIPS 2026 D&B: jsonld-ex full evaluation (submitted)
- This paper: HIPAA compliance algebra + HE (new, distinct contributions)
