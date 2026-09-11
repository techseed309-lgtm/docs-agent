# corpus/sample — sources and licensing

Sample corpus for docs-agent: 15 NIST cybersecurity-compliance publications. Chosen
per [PLAN.md](../../PLAN.md) M1/pre-check-3 as the demo's target sector — MSPs, security
consultancies, and any company doing SOC2/NIST/CMMC work.

## Licence

All documents below are NIST Special Publications or Cybersecurity White Papers,
authored by the National Institute of Standards and Technology, an agency of the U.S.
federal government. As works of the U.S. federal government they are in the **public
domain** in the United States (17 U.S.C. §105 — no copyright protection is available
for works of the U.S. Government) and are published by NIST for free, unrestricted
public distribution. No attribution is legally required, though it's given below for
traceability.

Retrieved: 2026-09-11, directly from `nvlpubs.nist.gov` (NIST's own publication host).
Each is the current, non-withdrawn final version as of that date — NIST periodically
supersedes these with new revisions; re-check `csrc.nist.gov/pubs/sp800` before relying
on this list for anything beyond this demo.

## Documents

| File | Publication | Title | Date |
|---|---|---|---|
| `NIST.SP.800-63B-4.pdf` | SP 800-63B-4 | Digital Identity Guidelines: Authentication and Authenticator Management | Jul 2025 |
| `NIST.SP.800-171r3.pdf` | SP 800-171 Rev. 3 | Protecting Controlled Unclassified Information in Nonfederal Systems and Organizations | May 2024 |
| `NIST.SP.800-171Ar3.pdf` | SP 800-171A Rev. 3 | Assessing Security Requirements for Controlled Unclassified Information | May 2024 |
| `NIST.SP.800-61r3.pdf` | SP 800-61 Rev. 3 | Incident Response Recommendations and Considerations for Cybersecurity Risk Management: A CSF 2.0 Community Profile | Apr 2025 |
| `NIST.CSWP.29.pdf` | CSWP 29 | The NIST Cybersecurity Framework (CSF) 2.0 | Feb 2024 |
| `NIST.SP.800-207.pdf` | SP 800-207 | Zero Trust Architecture | Aug 2020 |
| `NIST.SP.800-88r1.pdf` | SP 800-88 Rev. 1 | Guidelines for Media Sanitization | Dec 2014 |
| `NIST.SP.800-128.pdf` | SP 800-128 | Guide for Security-Focused Configuration Management of Information Systems | Aug 2011 |
| `NIST.SP.800-83r1.pdf` | SP 800-83 Rev. 1 | Guide to Malware Incident Prevention and Handling for Desktops and Laptops | Jul 2013 |
| `NIST.SP.800-46r2.pdf` | SP 800-46 Rev. 2 | Guide to Enterprise Telework, Remote Access, and Bring Your Own Device (BYOD) Security | Jul 2016 |
| `NIST.SP.800-30r1.pdf` | SP 800-30 Rev. 1 | Guide for Conducting Risk Assessments | Sep 2012 |
| `NIST.SP.800-137.pdf` | SP 800-137 | Information Security Continuous Monitoring (ISCM) for Federal Information Systems and Organizations | Sep 2011 |
| `NIST.SP.800-18r2.pdf` | SP 800-18 Rev. 2 | Guide for Developing Security Plans for Federal Information Systems | 2024 |
| `NIST.SP.800-115.pdf` | SP 800-115 | Technical Guide to Information Security Testing and Assessment | Sep 2008 |
| `NIST.SP.800-92.pdf` | SP 800-92 | Guide to Computer Security Log Management | Sep 2006 |

## Why this set

Deliberately spans identity/authentication, CUI/compliance, incident response,
governance framework, zero trust, media sanitization, configuration management,
malware handling, telework/BYOD, risk assessment, continuous monitoring, security
planning, technical testing, and log management — enough topic spread that
`eval/golden.yaml` (M3) can ask real cross-document questions, and enough boundary
(anything outside NIST's own scope — HIPAA specifics, PCI-DSS, GDPR, vendor-specific
product docs) to construct genuine refusal cases rather than trivial ones.

## Retrieval commands (for reproducing this set)

```bash
curl -sL -o NIST.SP.800-63B-4.pdf   https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63b-4.pdf
curl -sL -o NIST.SP.800-171r3.pdf   https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-171r3.pdf
curl -sL -o NIST.SP.800-171Ar3.pdf  https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-171Ar3.pdf
curl -sL -o NIST.SP.800-61r3.pdf    https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf
curl -sL -o NIST.CSWP.29.pdf        https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf
curl -sL -o NIST.SP.800-207.pdf     https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-207.pdf
curl -sL -o NIST.SP.800-88r1.pdf    https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-88r1.pdf
curl -sL -o NIST.SP.800-128.pdf     https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-128.pdf
curl -sL -o NIST.SP.800-83r1.pdf    https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-83r1.pdf
curl -sL -o NIST.SP.800-46r2.pdf    https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-46r2.pdf
curl -sL -o NIST.SP.800-30r1.pdf    https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-30r1.pdf
curl -sL -o NIST.SP.800-137.pdf     https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-137.pdf
curl -sL -o NIST.SP.800-18r2.pdf    https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-18r2.pdf
curl -sL -o NIST.SP.800-115.pdf     https://nvlpubs.nist.gov/nistpubs/legacy/SP/nistspecialpublication800-115.pdf
curl -sL -o NIST.SP.800-92.pdf      https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-92.pdf
```
